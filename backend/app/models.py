from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON
from .database import Base

class Port(Base):
    """
    항구 및 좌표 정보를 저장하는 테이블
    Schema: TB_PORT
    """
    __tablename__ = "TB_PORT"

    port_code = Column(String, primary_key=True, index=True, comment="항만코드 (PK, UN/LOCODE)")
    port_name = Column(String, nullable=False, index=True, comment="항만명")
    # 정밀도 확보를 위해 Numeric 사용 권장, 편의상 Float 사용 시 오차 주의
    lat = Column(Float, nullable=False, comment="위도")
    lng = Column(Float, nullable=False, comment="경도")
    nation_name = Column(String, nullable=True, comment="항만의 소속 국가")
    aliases = Column(JSON, nullable=True, comment="항구명 별칭 목록 (JSON)")
    port_info = Column(JSON, nullable=True, comment="항만 정보 (JSON 형태: 연락처, 수심 등)")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="생성일")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="수정일")

    # Relationships
    # Note: TB_PROFORMA와의 직접적인 FK 연결은 TB_PROFORMA에 port_code가 없으므로 생략 가능하나,
    # 필요 시 시각화를 위해 매핑 로직에서 사용됨.

class Route(Base):
    """
    노선(항로) 정보를 저장하는 테이블
    Schema: TB_ROUTE
    """
    __tablename__ = "TB_ROUTE"

    route_idx = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="노선 인덱스 (PK)")
    year = Column(Integer, index=True, nullable=False, default=2026, comment="기항 노선 기준 연도")
    svc = Column(String, index=True, nullable=True, comment="서비스 코드 (BPA SERVICE CODE)")
    route_name = Column(String, nullable=True, comment="노선명")
    
    region_idx = Column(Integer, nullable=False, default=0, comment="운항 지역 인덱스")
    region = Column(String, nullable=True, comment="운항 지역")
    sort_idx = Column(Integer, nullable=False, default=0, comment="정렬 인덱스")
    
    carriers = Column(String, nullable=True, comment="선사명 목록")
    port_rotation = Column(Text, nullable=True, comment="기항지 순서 (Raw Text)")
    frequency = Column(String, nullable=True, comment="운항 빈도")
    duration = Column(Integer, nullable=True, comment="운항 기간")
    ships = Column(String, nullable=True, comment="투입 선박 정보")

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="수정일")

    # Relationships
    proforma = relationship("Proforma", back_populates="route", cascade="all, delete-orphan")

class Proforma(Base):
    """
    노선별 부산항 상,하역 터미널 정보를 저장하는 테이블
    Schema: TB_PROFORMA
    """
    __tablename__ = "TB_PROFORMA"

    term_id = Column(Integer, primary_key=True, index=True, autoincrement=True, comment="ID (PK)")
    route_idx = Column(Integer, ForeignKey("TB_ROUTE.route_idx"), nullable=False, comment="노선 인덱스 (FK)")
    
    svc = Column(String, nullable=True, comment="서브 노선 식별자")
    terminal_name = Column(String, nullable=False, comment="부산항 기항 시 상,하역 터미널명 (구 t1_name)")
    wtp = Column(String, nullable=True, comment="WTP (Weekly Throughput)")
    sch = Column(String, nullable=True, comment="스케줄 (부산항 입출항)")
    seq = Column(Integer, nullable=False, comment="터미널 순서")

    # Relationships
    route = relationship("Route", back_populates="proforma")
