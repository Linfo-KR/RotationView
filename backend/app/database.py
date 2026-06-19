"""
데이터베이스 연결 설정.

환경변수(.env)에서 DB 접속 정보를 읽어 SQLAlchemy 엔진을 구성합니다.
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# .env 파일에서 환경변수 로드
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

SQLALCHEMY_DATABASE_URL = URL.create(
    drivername="postgresql",
    username=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", ""),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME", "rotation_db"),
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI Dependency: 각 요청마다 DB 세션을 생성하고 종료합니다."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
