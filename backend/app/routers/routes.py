"""
노선(Route) 관련 API 라우터.

노선 목록 조회, 상세 조회, 항구 매칭 오류 수정 등의 엔드포인트를 제공합니다.
"""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from .. import models, schemas
from ..services.geometry import get_or_compute_geometry

router = APIRouter(prefix="/api", tags=["routes"])


@router.get("/routes/years", response_model=List[int])
def read_route_years(db: Session = Depends(get_db)) -> List[int]:
    """DB에 등록된 고유한 노선 기준 연도 목록을 내림차순으로 반환합니다."""
    years_db = (
        db.query(models.Route.year)
        .distinct()
        .order_by(models.Route.year.desc())
        .all()
    )
    return [y[0] for y in years_db]


@router.get("/routes", response_model=List[schemas.Route])
def read_routes(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = Query(None, description="노선명 또는 서비스 코드로 검색"),
    year: Optional[int] = Query(None, description="조회할 노선 기준 연도"),
    db: Session = Depends(get_db),
):
    """모든 노선(Route) 목록을 조회합니다.

    캐시된 지오메트리를 우선 사용하여 응답 속도를 최적화합니다.
    """
    query = db.query(models.Route)

    if year is not None:
        query = query.filter(models.Route.year == year)
    else:
        # year가 주어지지 않으면 DB에서 가장 최신의 연도를 찾아서 기본 필터로 적용
        max_year = db.query(func.max(models.Route.year)).scalar()
        if max_year is not None:
            query = query.filter(models.Route.year == max_year)

    if search:
        query = query.filter(
            (models.Route.route_name.contains(search))
            | (models.Route.svc.contains(search))
        )

    routes_db = query.offset(skip).limit(limit).all()

    routes_response = []
    for route_db in routes_db:
        route_schema = schemas.Route.model_validate(route_db)
        # 목록 조회에서는 지오메트리를 포함하지 않음 (성능 최적화)
        # 지오메트리는 개별 노선 조회(/routes/{id})에서만 계산하여 제공
        route_schema.line_geometry = None
        routes_response.append(route_schema)

    return routes_response


@router.get("/routes/{route_idx}", response_model=schemas.Route)
def read_route(route_idx: int, db: Session = Depends(get_db)):
    """특정 노선의 상세 정보와 기항지(Proforma) 정보를 조회합니다."""
    route_db = (
        db.query(models.Route)
        .filter(models.Route.route_idx == route_idx)
        .first()
    )
    if route_db is None:
        raise HTTPException(status_code=404, detail="Route not found")

    route_schema = schemas.Route.model_validate(route_db)

    if route_db.port_rotation:
        route_schema.line_geometry = get_or_compute_geometry(
            db, route_db.route_idx, route_db.port_rotation
        )

    return route_schema


@router.post("/fix-port-mismatch")
def fix_port_mismatch(
    fix_data: schemas.PortMismatchFix, db: Session = Depends(get_db)
):
    """오타가 있는 항구명을 올바른 항구 코드에 별칭(Alias)으로 등록하고,
    해당 노선의 port_rotation을 수정합니다.
    """
    # 1. 올바른 항구 조회
    port = (
        db.query(models.Port)
        .filter(models.Port.port_code == fix_data.correct_port_code)
        .first()
    )
    if not port:
        raise HTTPException(status_code=404, detail="Correct port not found")

    # 2. Aliases 업데이트
    aliases = []
    if port.aliases:
        if isinstance(port.aliases, list):
            aliases = port.aliases
        elif isinstance(port.aliases, str):
            try:
                aliases = json.loads(port.aliases)
            except (json.JSONDecodeError, ValueError):
                aliases = []

    normalized_bad_name = fix_data.bad_port_name.strip()
    if not any(a.lower() == normalized_bad_name.lower() for a in aliases):
        aliases.append(normalized_bad_name)
        port.aliases = aliases

    # 3. Route Rotation 업데이트
    route = (
        db.query(models.Route)
        .filter(models.Route.route_idx == fix_data.route_idx)
        .first()
    )
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    if route.port_rotation:
        new_rotation = route.port_rotation.replace(
            fix_data.bad_port_name, port.port_name
        )
        route.port_rotation = new_rotation

    db.commit()
    db.refresh(port)
    db.refresh(route)

    return {
        "status": "success",
        "message": f"Mapped '{fix_data.bad_port_name}' to '{port.port_name}' and updated route.",
    }
