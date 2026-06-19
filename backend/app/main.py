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
from .services.geometry import get_or_compute_geometry

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


def prewarm_geometry_cache() -> None:
    """백그라운드 스레드에서 캐시가 비어 있는 노선의 경로 데이터를 선제적으로 계산하여 저장합니다."""
    db = SessionLocal()
    try:
        routes_db = db.query(models.Route).all()
        print(f"[Prewarm] Starting background cache pre-warm for {len(routes_db)} routes...")
        count = 0
        for r in routes_db:
            if r.port_rotation:
                # get_or_compute_geometry 내부에서 캐시 유무 체크 후 없으면 계산함
                get_or_compute_geometry(db, r.route_idx, r.port_rotation)
                count += 1
                time.sleep(0.02)  # CPU 부하 분산
        print(f"[Prewarm] Finished background cache pre-warm. Processed {count} routes.")
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