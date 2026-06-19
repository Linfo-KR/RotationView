"""
항구 좌표 매칭 서비스.

port_rotation 문자열의 항만명을 DB의 TB_PORT 데이터와 매칭하여
좌표를 반환하는 기능을 제공합니다.
"""
import re
import json
from typing import Optional, Tuple, List

from sqlalchemy.orm import Session

from ..models import Port


def get_port_coords(db: Session, port_name: str) -> Tuple[Optional[float], Optional[float]]:
    """항만명으로 좌표(lat, lng)를 조회합니다.

    정확한 이름 매칭을 먼저 시도하고, 실패 시 aliases(별칭) 매칭을 수행합니다.

    Args:
        db: SQLAlchemy 세션
        port_name: 검색할 항만명

    Returns:
        (lat, lng) 튜플. 매칭 실패 시 (None, None)
    """
    normalized_name = re.sub(r'\(.*?\)', '', port_name).strip().lower()

    # 1차: 정확한 이름 매칭
    port = db.query(Port).filter(Port.port_name.ilike(normalized_name)).first()
    if port:
        return port.lat, port.lng

    # 2차: aliases(별칭) 매칭
    ports_with_aliases = db.query(Port).filter(Port.aliases.isnot(None)).all()
    for p in ports_with_aliases:
        try:
            aliases = p.aliases
            if not isinstance(aliases, list):
                aliases = json.loads(aliases) if isinstance(aliases, str) else []
            if any(alias.lower() == normalized_name for alias in aliases):
                return p.lat, p.lng
        except (json.JSONDecodeError, TypeError):
            continue

    return None, None


def parse_port_rotation(port_rotation: str) -> List[str]:
    """port_rotation 문자열을 파싱하여 항만명 리스트를 반환합니다.

    Args:
        port_rotation: 쉼표/하이픈/화살표로 구분된 항만 순서 문자열

    Returns:
        공백이 제거된 항만명 리스트
    """
    port_names = re.split(r'[,\->]+', port_rotation)
    return [p.strip() for p in port_names if p.strip()]
