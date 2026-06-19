"""기하학 캐시 테이블을 비우기 위한 유틸리티 스크립트.
"""
import sys
import os
from sqlalchemy import text

# backend 디렉토리를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal


def clear_geometry_cache() -> None:
    """TB_ROUTE_GEOMETRY 캐시 테이블을 비웁니다."""
    db = SessionLocal()
    try:
        db.execute(text('TRUNCATE TABLE "TB_ROUTE_GEOMETRY";'))
        db.commit()
        print("Successfully cleared TB_ROUTE_GEOMETRY table.")
    except Exception as e:
        db.rollback()
        print(f"[Error] Failed to clear cache: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    clear_geometry_cache()
