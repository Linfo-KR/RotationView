"""
RotationView API 서버.

FastAPI 앱을 초기화하고 라우터를 등록합니다.
캐싱 테이블 자동 생성 및 CORS 미들웨어를 설정합니다.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import threading
import time

from .database import engine, SessionLocal
from . import models
from .routers import routes, ports
from .services.geometry import get_or_compute_geometry, _hash_rotation, calculate_route_geometry, save_geometry_cache
from concurrent.futures import ThreadPoolExecutor

# DB 테이블 생성 (서버 시작 시 자동 생성)
models.Base.metadata.create_all(bind=engine)

# 캐싱 테이블 생성 (ORM 미사용, DDL 직접 실행)
with engine.connect() as conn:
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS "TB_ROUTE_GEOMETRY" (
            route_idx INTEGER PRIMARY KEY REFERENCES "TB_ROUTE"(route_idx),
            outbound_geojson TEXT,
            inbound_geojson TEXT,
            arrow_points TEXT,
            total_distance_km FLOAT,
            port_rotation_hash VARCHAR(64),
            computed_at TIMESTAMP DEFAULT NOW()
        )
    '''))
    conn.commit()

app = FastAPI(title="RotationView API", version="1.0.0")

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

# 라우터 등록
app.include_router(routes.router)
app.include_router(ports.router)


@app.get("/")
def read_root():
    """루트 엔드포인트."""
    return {"message": "Welcome to RotationView API. Visit /docs for API documentation."}


@app.get("/api/health")
def health_check():
    """헬스 체크 엔드포인트."""
    return {"status": "ok"}


@app.post("/api/cache/rebuild")
def rebuild_cache():
    """모든 노선의 지오메트리 캐시를 재구축합니다.

    기존 캐시를 모두 삭제하고, 다음 조회 시 자동으로 재계산됩니다.
    """
    with engine.connect() as conn:
        conn.execute(text('DELETE FROM "TB_ROUTE_GEOMETRY"'))
        conn.commit()
    return {"status": "ok", "message": "Cache cleared. Will rebuild on next query."}


def prewarm_route_worker(route_idx: int, port_rotation: str) -> None:
    """단일 노선의 지오메트리를 계산하여 캐시에 저장하는 워커 스레드 함수입니다."""
    db = SessionLocal()
    try:
        geometry = calculate_route_geometry(db, port_rotation)
        save_geometry_cache(db, route_idx, port_rotation, geometry)
    except Exception as e:
        print(f"[Prewarm-Worker] Error computing route {route_idx}: {e}")
    finally:
        db.close()


def prewarm_geometry_cache() -> None:
    """멀티스레드 병렬화 및 일괄(Batch) 조회를 통해 캐시 프리워밍 성능을 극대화합니다."""
    db = SessionLocal()
    try:
        routes_db = db.query(models.Route).all()
        print(f"[Prewarm] Starting optimized background cache pre-warm for {len(routes_db)} routes...")

        # 1. 기존 캐시의 해시값 일괄(Batch) SELECT로 인메모리 로딩 (DB 단건 500회 SELECT 병목 제거)
        cached_rows = db.execute(
            text('SELECT route_idx, port_rotation_hash FROM "TB_ROUTE_GEOMETRY"')
        ).fetchall()
        cached_hashes = {row[0]: row[1] for row in cached_rows}

        # 2. 프리워밍 대상(캐시 부재 또는 해시 불일치) 필터링
        to_warm = []
        for r in routes_db:
            if not r.port_rotation:
                continue
            
            curr_hash = _hash_rotation(r.port_rotation)
            if cached_hashes.get(r.route_idx) != curr_hash:
                to_warm.append((r.route_idx, r.port_rotation))

        print(f"[Prewarm] Filtered {len(to_warm)} routes requiring calculation.")

        # 3. ThreadPoolExecutor를 사용한 멀티스레드 병렬 연산 (CPU/네트워크 분산)
        if to_warm:
            # 4개의 워커 스레드로 병렬 연산 수행
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(prewarm_route_worker, idx, rot)
                    for idx, rot in to_warm
                ]
                # 모든 작업이 완료될 때까지 대기
                for fut in futures:
                    fut.result()

        print(f"[Prewarm] Finished background cache pre-warm successfully. (Warmed {len(to_warm)} routes)")
    except Exception as e:
        print(f"[Prewarm] Error during cache pre-warming: {e}")
    finally:
        db.close()


def start_prewarm_thread() -> None:
    """캐시 선행 연산을 비동기 데몬 스레드로 기동합니다."""
    thread = threading.Thread(target=prewarm_geometry_cache, daemon=True)
    thread.start()


@app.on_event("startup")
def startup_event() -> None:
    """FastAPI 서버 구동 시 프리워머 스레드를 실행시킵니다."""
    start_prewarm_thread()