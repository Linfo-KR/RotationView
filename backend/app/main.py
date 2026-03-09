from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import searoute as sr # Import searoute library
import re # For parsing port names
import json # Import json for parsing aliases

from . import models, schemas
from .database import SessionLocal, engine
from fastapi.middleware.cors import CORSMiddleware

# DB 테이블 생성 (서버 시작 시 자동 생성)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="RotationView API", version="0.1.0")

# CORS 설정
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://localhost:3000",  # React default
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency: 각 요청마다 DB 세션을 열고 닫음
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper function to get port coordinates by name (considering aliases)
# This will be used to map port names from rotation to lat/lng for searoute
def get_port_coords(db: Session, port_name: str):
    normalized_name = re.sub(r'\(.*?\)', '', port_name).strip().lower()
    
    # Try exact match first
    port = db.query(models.Port).filter(models.Port.port_name.ilike(normalized_name)).first()
    if port:
        return port.lat, port.lng

    # Then try aliases (if stored as JSON list in DB)
    # This assumes aliases are stored as a JSON string like '["alias1", "alias2"]'
    ports_with_aliases = db.query(models.Port).filter(models.Port.aliases.isnot(None)).all()
    for p in ports_with_aliases:
        try:
            aliases = p.aliases # This should already be parsed as a list by SQLAlchemy if JSON type is used
            if not isinstance(aliases, list): # Fallback for string-stored JSON
                aliases = json.loads(aliases) if isinstance(aliases, str) else []
            if any(alias.lower() == normalized_name for alias in aliases):
                return p.lat, p.lng
        except (json.JSONDecodeError, TypeError):
            continue # Ignore if aliases is not valid JSON
            
    return None, None # Not found

def unwrap_coordinates(coords):
    """
    Fixes the dateline crossing issue by ensuring longitude continuity.
    If the longitude jumps by more than 180 degrees, add/subtract 360 to make it continuous.
    """
    if not coords:
        return []
    
    unwrapped = [coords[0]]
    for i in range(1, len(coords)):
        prev = unwrapped[-1]
        curr = list(coords[i]) # Copy to avoid modifying original if needed
        
        # Calculate longitude difference
        lon_diff = curr[0] - prev[0]
        
        # Adjust longitude if the jump is too big (crossing the antimeridian)
        if lon_diff > 180:
            curr[0] -= 360
        elif lon_diff < -180:
            curr[0] += 360
            
        unwrapped.append(curr)
        
    return unwrapped

# Helper function to calculate full route geometry
def calculate_route_geometry(db: Session, port_rotation: str):
    port_names = re.split(r'[,\->]+', port_rotation)
    port_names = [p.strip() for p in port_names if p.strip()]
    
    coords_list = []
    for name in port_names:
        lat, lng = get_port_coords(db, name)
        if lat is not None and lng is not None:
            coords_list.append([lng, lat]) # searoute expects [lng, lat]
            
    if len(coords_list) < 2:
        return []

    full_geometry = []
    
    # Calculate path for each segment (A->B, B->C, etc.)
    for i in range(len(coords_list) - 1):
        origin = coords_list[i]
        dest = coords_list[i+1]
        
        try:
            # Calculate segment
            segment_geom = sr.searoute(origin, dest, append_orig_dest=True)
            
            segment_coords = []
            
            # Handle different geometry types (LineString or MultiLineString)
            if segment_geom:
                geom = segment_geom.get('geometry') or (segment_geom.get('features')[0].get('geometry') if segment_geom.get('features') else None)
                
                if geom:
                    if geom['type'] == 'LineString':
                        segment_coords = geom['coordinates']
                    elif geom['type'] == 'MultiLineString':
                        # Flatten MultiLineString into a single list of coordinates
                        # Note: This might create "jumps" if the lines are not connected, 
                        # but unwrap_coordinates should handle visual continuity for date line.
                        for line in geom['coordinates']:
                            segment_coords.extend(line)
            
            if segment_coords:
                # If not the first segment, remove the first point to avoid duplication with previous segment's last point
                if i > 0 and full_geometry:
                    # Basic check to skip if identical
                    if full_geometry[-1] == [segment_coords[0][1], segment_coords[0][0]]: 
                         segment_coords = segment_coords[1:]
                    # Also check against raw searched coords logic if needed, but strict index slicing is safer
                    elif len(segment_coords) > 0:
                         segment_coords = segment_coords[1:]

                # Convert [lng, lat] to [lat, lng]
                # We do NOT convert here yet if we want to run unwrap_coordinates on [lng, lat].
                # Standard is usually [lng, lat] for geojson operations.
                # Let's keep it as [lng, lat] for unwrapping, then flip at the very end.
                
                # However, full_geometry in previous step was storing [lat, lng]. 
                # Let's standardize full_geometry to store [lat, lng] to match frontend expectation immediately,
                # BUT unwrap logic works best on Longitude (index 0 or 1). 
                
                # REVISED STRATEGY: 
                # 1. Get segment coords in [lng, lat]
                # 2. Unwrap THIS segment relative to the LAST point of full_geometry (if exists)
                
                current_segment_latlng = []
                for c in segment_coords:
                    current_segment_latlng.append([c[1], c[0]]) # [lat, lng]

                full_geometry.extend(current_segment_latlng)
                
        except Exception as e:
            print(f"Error calculating searoute segment {i}: {e}")
            pass

    # Apply global unwrapping on the final [lat, lng] list
    # Note: unwrapping expects [lng, lat] logic usually, so we pass index 1 as longitude
    
    if not full_geometry:
        return []

    # Custom unwrapper for [lat, lng] format
    final_coords = [full_geometry[0]]
    for k in range(1, len(full_geometry)):
        prev = final_coords[-1]
        curr = list(full_geometry[k])
        
        # Longitude is at index 1
        lon_diff = curr[1] - prev[1]
        
        if lon_diff > 180:
            curr[1] -= 360
        elif lon_diff < -180:
            curr[1] += 360
            
        final_coords.append(curr)

    return final_coords

@app.post("/api/fix-port-mismatch")
def fix_port_mismatch(fix_data: schemas.PortMismatchFix, db: Session = Depends(get_db)):
    """
    오타가 있는 항구명을 올바른 항구 코드에 별칭(Alias)으로 등록하고,
    해당 노선의 port_rotation을 수정합니다.
    """
    # 1. Find the correct port
    port = db.query(models.Port).filter(models.Port.port_code == fix_data.correct_port_code).first()
    if not port:
        raise HTTPException(status_code=404, detail="Correct port not found")
    
    # 2. Update Aliases
    aliases = []
    if port.aliases:
        if isinstance(port.aliases, list):
            aliases = port.aliases
        elif isinstance(port.aliases, str):
            try:
                aliases = json.loads(port.aliases)
            except:
                aliases = []
    
    # Add new alias if not exists
    normalized_bad_name = fix_data.bad_port_name.strip()
    # Check case-insensitive
    if not any(a.lower() == normalized_bad_name.lower() for a in aliases):
        aliases.append(normalized_bad_name)
        port.aliases = aliases # SQLAlchmey detects change if using MutableList or re-assigning
        # If aliases column is just JSON, re-assigning works.
        
        # Explicitly flag modified for some SA versions if needed, but re-assign usually works
    
    # 3. Update Route Rotation
    route = db.query(models.Route).filter(models.Route.route_idx == fix_data.route_idx).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Replace the bad name in the rotation string
    # We use regex to ensure we replace the exact term (handling boundaries if possible)
    # But names can be tricky. Simple string replace might be safer for now if the name is unique enough.
    if route.port_rotation:
        # Regex replacement to match whole words or comma-separated parts ideally
        # Trying a simple replace first.
        # But 'Long Beach' vs 'Long Beach/Los Angeles'.
        # If we replace 'Long Beach/Los Angeles' with 'Los Angeles', it works.
        new_rotation = route.port_rotation.replace(fix_data.bad_port_name, port.port_name)
        route.port_rotation = new_rotation
        
    db.commit()
    db.refresh(port)
    db.refresh(route)
    
    return {"status": "success", "message": f"Mapped '{fix_data.bad_port_name}' to '{port.port_name}' and updated route."}


@app.get("/")
def read_root():
    return {"message": "Welcome to RotationView API. Visit /docs for API documentation."}

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

# --- Routes API ---

@app.get("/api/routes", response_model=List[schemas.Route])
def read_routes(
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = Query(None, description="노선명 또는 서비스 코드로 검색"),
    db: Session = Depends(get_db)
):
    """
    모든 노선(Route) 목록을 조회합니다.
    """
    query = db.query(models.Route)
    
    if search:
        query = query.filter(
            (models.Route.route_name.contains(search)) | 
            (models.Route.svc.contains(search))
        )
        
    routes_db = query.offset(skip).limit(limit).all()
    
    # Convert ORM models to Pydantic schemas and calculate route geometry
    routes_response = []
    for route_db in routes_db:
        route_schema = schemas.Route.model_validate(route_db)
        
        # Calculate full route geometry
        route_schema.line_geometry = calculate_route_geometry(db, route_db.port_rotation)
        
        routes_response.append(route_schema)

    return routes_response


@app.get("/api/routes/{route_idx}", response_model=schemas.Route)
def read_route(route_idx: int, db: Session = Depends(get_db)):
    """
    특정 노선의 상세 정보와 기항지(Proforma) 정보를 조회합니다.
    """
    route_db = db.query(models.Route).filter(models.Route.route_idx == route_idx).first()
    if route_db is None:
        raise HTTPException(status_code=404, detail="Route not found")
    
    route_schema = schemas.Route.model_validate(route_db)
    
    # Calculate full route geometry
    route_schema.line_geometry = calculate_route_geometry(db, route_db.port_rotation)

    return route_schema


# --- Ports API ---

@app.get("/api/ports", response_model=List[schemas.Port])
def read_ports(
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = Query(None, description="항구명 또는 코드로 검색"),
    db: Session = Depends(get_db)
):
    """
    모든 항구 목록을 조회합니다.
    """
    query = db.query(models.Port)
    
    if search:
        query = query.filter(
            (models.Port.port_name.contains(search)) | 
            (models.Port.port_code.contains(search))
        )
        
    ports = query.offset(skip).limit(limit).all()
    return ports

@app.get("/api/ports/{port_code}", response_model=schemas.Port)
def read_port(port_code: str, db: Session = Depends(get_db)):
    """
    특정 항구의 상세 정보를 조회합니다.
    """
    port = db.query(models.Port).filter(models.Port.port_code == port_code).first()
    if port is None:
        raise HTTPException(status_code=404, detail="Port not found")
    return port