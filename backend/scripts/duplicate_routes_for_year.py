"""
2025년도 데이터를 기반으로 다른 년도의 노선도 데이터를 복사하여 삽입하는 스크립트.
"""
import sys
import os
from sqlalchemy import text

# backend 디렉토리를 sys.path에 추가하여 app 패키지를 가져올 수 있도록 합니다.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Route, Proforma


def sync_sequence_values() -> None:
    """PostgreSQL의 TB_ROUTE 및 TB_PROFORMA 테이블의 primary key sequence 값을

    현재 테이블에 존재하는 최대값에 맞춰 동기화합니다.
    """
    db = SessionLocal()
    try:
        # DB 엔진 정보를 통해 sequence 갱신 쿼리 실행
        db.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('\"TB_ROUTE\"', 'route_idx'), COALESCE(MAX(route_idx), 0) + 1, false) FROM \"TB_ROUTE\";"
            )
        )
        db.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('\"TB_PROFORMA\"', 'term_id'), COALESCE(MAX(term_id), 0) + 1, false) FROM \"TB_PROFORMA\";"
            )
        )
        db.commit()
        print("Sequence values successfully synchronized.")
    except Exception as e:
        db.rollback()
        print(f"[Error] Failed to synchronize sequences: {e}")
    finally:
        db.close()


def duplicate_route_data(source_year: int, target_year: int) -> None:
    """지정한 원본 연도(source_year)의 노선 데이터를 대상 연도(target_year)의 데이터로 복제하여 DB에 삽입합니다.

    Args:
        source_year (int): 복제 대상이 되는 원본 연도
        target_year (int): 데이터를 삽입할 대상 연도
    """
    db = SessionLocal()
    try:
        # 기존 target_year 데이터가 이미 있는지 확인
        existing_count = db.query(Route).filter(Route.year == target_year).count()
        if existing_count > 0:
            print(f"[Warning] {target_year}년도 노선 데이터가 이미 {existing_count}개 존재합니다.")
            return

        # source_year 데이터 조회
        source_routes = db.query(Route).filter(Route.year == source_year).all()
        if not source_routes:
            print(f"[Error] {source_year}년도 노선 데이터를 찾을 수 없습니다.")
            return

        print(f"복제 시작: {source_year}년 ({len(source_routes)}개 노선) -> {target_year}년")

        copied_routes_count = 0
        copied_proformas_count = 0

        for route in source_routes:
            # Route 데이터 복제
            new_route = Route(
                year=target_year,
                svc=route.svc,
                route_name=route.route_name,
                region_idx=route.region_idx,
                region=route.region,
                sort_idx=route.sort_idx,
                carriers=route.carriers,
                port_rotation=route.port_rotation,
                frequency=route.frequency,
                duration=route.duration,
                ships=route.ships,
            )
            db.add(new_route)
            db.flush()  # new_route.route_idx 생성 유도

            # Proforma 데이터 복제
            for proforma in route.proforma:
                new_proforma = Proforma(
                    route_idx=new_route.route_idx,
                    svc=proforma.svc,
                    terminal_name=proforma.terminal_name,
                    wtp=proforma.wtp,
                    sch=proforma.sch,
                    seq=proforma.seq,
                )
                db.add(new_proforma)
                copied_proformas_count += 1

            copied_routes_count += 1

        db.commit()
        print(f"복제 완료: {target_year}년 노선 {copied_routes_count}개, 터미널 정보 {copied_proformas_count}개 추가됨.")
    except Exception as e:
        db.rollback()
        print(f"[Error] 복제 중 에러 발생: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    sync_sequence_values()
    duplicate_route_data(2025, 2026)
