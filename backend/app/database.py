from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 개발 단계에서는 SQLite를 사용하고, 프로덕션에서는 PostgreSQL 사용을 권장합니다.
# 현재는 파일 기반 SQLite DB로 빠르게 프로토타이핑합니다.
SQLALCHEMY_DATABASE_URL = "sqlite:///./rotationview.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
