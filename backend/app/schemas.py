from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime

# --- Port Schemas ---
class PortBase(BaseModel):
    port_name: str
    lat: float
    lng: float
    nation_name: Optional[str] = None
    aliases: Optional[List[str]] = None
    port_info: Optional[Any] = None

class PortCreate(PortBase):
    port_code: str

class Port(PortBase):
    port_code: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Proforma Schemas ---
class ProformaBase(BaseModel):
    seq: int
    terminal_name: str
    wtp: Optional[str] = None
    sch: Optional[str] = None
    svc: Optional[str] = None # 단순 정보성 필드

class ProformaCreate(ProformaBase):
    route_idx: int

class Proforma(ProformaBase):
    term_id: int
    route_idx: int
    
    class Config:
        from_attributes = True

# --- Route Schemas ---
class RouteBase(BaseModel):
    year: int = 2026
    svc: Optional[str] = None
    route_name: Optional[str] = None
    region_idx: int = 0
    region: Optional[str] = None
    sort_idx: int = 0
    carriers: Optional[str] = None
    port_rotation: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[int] = None
    ships: Optional[str] = None

class RouteCreate(RouteBase):
    pass

class Route(RouteBase):
    route_idx: int
    updated_at: Optional[datetime] = None
    proforma: List[Proforma] = []
    line_geometry: Optional[Any] = None  # Route geometry (outbound, inbound, arrows)

    class Config:
        from_attributes = True

class PortMismatchFix(BaseModel):
    route_idx: int
    bad_port_name: str
    correct_port_code: str
