"""
항구(Port) 관련 API 라우터.

항구 목록 조회, 상세 조회 등의 엔드포인트를 제공합니다.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/api", tags=["ports"])


@router.get("/ports", response_model=List[schemas.Port])
def read_ports(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = Query(None, description="항구명 또는 코드로 검색"),
    db: Session = Depends(get_db),
):
    """모든 항구 목록을 조회합니다."""
    query = db.query(models.Port)

    if search:
        query = query.filter(
            (models.Port.port_name.contains(search))
            | (models.Port.port_code.contains(search))
        )

    ports = query.offset(skip).limit(limit).all()
    return ports


@router.get("/ports/{port_code}", response_model=schemas.Port)
def read_port(port_code: str, db: Session = Depends(get_db)):
    """특정 항구의 상세 정보를 조회합니다."""
    port = (
        db.query(models.Port)
        .filter(models.Port.port_code == port_code)
        .first()
    )
    if port is None:
        raise HTTPException(status_code=404, detail="Port not found")
    return port
