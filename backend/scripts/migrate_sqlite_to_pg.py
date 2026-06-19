import os
import sys
import sqlite3
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.models import Base, Port, Route, Proforma

def migrate(pg_user, pg_password, pg_host="localhost", pg_port="5432", pg_db="rotation_db"):
    # 스크립트 위치: backend/scripts
    # 최상위 루트 디렉터리에 원본 rotationview.db가 존재함 (이전 크기 약 1.1MB 짜리)
    sqlite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "rotationview.db")
    
    if not os.path.exists(sqlite_path):
        print(f"오류: 기존 SQLite DB를 찾을 수 없습니다. ({sqlite_path})")
        return
        
    print(f"1. SQLite 데이터 추출 중... ({sqlite_path})")
    conn_sqlite = sqlite3.connect(sqlite_path)
    
    # Read tables into DataFrames
    df_port = pd.read_sql_query("SELECT * FROM TB_PORT", conn_sqlite)
    df_route = pd.read_sql_query("SELECT * FROM TB_ROUTE", conn_sqlite)
    df_proforma = pd.read_sql_query("SELECT * FROM TB_PROFORMA", conn_sqlite)
    conn_sqlite.close()
    
    # default year for existing route data
    if 'year' not in df_route.columns:
        df_route['year'] = 2025

    print(f"2. PostgreSQL 연결 및 스키마 초기화 중...")
    pg_url = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
    # Windows/psycopg2 specific fix: explicit host parameter sometimes works better than URL for local sockets
    import urllib.parse
    safe_pw = urllib.parse.quote_plus(pg_password)
    pg_url = f"postgresql://{pg_user}:{safe_pw}@{pg_host}:{pg_port}/{pg_db}"
    engine = create_engine(pg_url)
    
    # Create tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    print("3. 데이터 마이그레이션 중...")
    
    # Use to_sql to easily insert data
    try:
        df_port.to_sql("TB_PORT", engine, if_exists="append", index=False)
        print(f"   TB_PORT 이관 완료 ({len(df_port)} 건)")
        
        df_route.to_sql("TB_ROUTE", engine, if_exists="append", index=False)
        print(f"   TB_ROUTE 이관 완료 ({len(df_route)} 건)")
        
        df_proforma.to_sql("TB_PROFORMA", engine, if_exists="append", index=False)
        print(f"   TB_PROFORMA 이관 완료 ({len(df_proforma)} 건)")
        
        print("\n마이그레이션이 성공적으로 완료되었습니다!")
    except Exception as e:
        print(f"마이그레이션 실패: {e}")

if __name__ == "__main__":
    print("====================================")
    print(" SQLite -> PostgreSQL 마이그레이션 ")
    print("====================================")
    
    # Use simple terminal input
    pg_user = input("PostgreSQL 사용자명 (기본: postgres): ") or "postgres"
    pg_password = input("PostgreSQL 비밀번호: ")
    pg_db = input("PostgreSQL 대상 DB (기본: rotation_db): ") or "rotation_db"
    
    migrate(pg_user, pg_password, pg_db=pg_db)
