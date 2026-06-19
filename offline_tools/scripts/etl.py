import pandas as pd
import sys
import os
import json
import numpy as np
from sqlalchemy.orm import Session
from datetime import datetime

# 현재 스크립트 위치를 기준으로 backend 모듈 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.database import SessionLocal, engine, Base
from backend.app.models import Port, Proforma, Route

# --- 파일 경로 설정 ---
FILE_PATHS = {
    "tb_port": "data/database/tb_port.csv",
    "tb_route": "data/database/tb_route.csv",
    "tb_proforma": "data/database/tb_proforma.csv",
}

# --- Helper Functions ---
def clean_float(value):
    """문자열이나 숫자에서 float 값을 안전하게 추출"""
    try:
        if pd.isna(value): return 0.0
        return float(value)
    except:
        return 0.0

def clean_str(value):
    """문자열 정제 (NaN 처리)"""
    if pd.isna(value): return None
    val = str(value).strip()
    return val if val else None

def clean_int(value):
    """정수 변환"""
    try:
        if pd.isna(value): return 0
        return int(float(value)) 
    except:
        return 0

# --- ETL Logic ---

def load_ports(db: Session, filepath: str):
    """
    tb_port.csv 파일을 읽어 TB_PORT 테이블에 적재
    동일한 port_code를 가진 경우, 첫 번째 행을 기준으로 저장하고
    나머지 이름들은 aliases 컬럼에 리스트로 저장함.
    """
    print(f"Loading Ports from {filepath}...")
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Failed to read {filepath}: {e}")
        return

    # port_code가 없는 행 제거
    df = df[df['port_code'].notna()]
    df['port_code'] = df['port_code'].astype(str).str.strip()

    # 기존 데이터 확인 (Upsert 처리를 위해)
    existing_ports = {p.port_code: p for p in db.query(Port).all()}
    
    new_ports = []
    updated_count = 0

    # port_code별로 그룹화
    grouped = df.groupby('port_code')

    for p_code, group in grouped:
        # 첫 번째 행을 대표 데이터로 사용
        first_row = group.iloc[0]
        
        # 모든 port_name 수집 (중복 제거)
        all_names = set(group['port_name'].dropna().astype(str).str.strip())
        
        # 대표 이름 설정
        p_name = clean_str(first_row.get('port_name'))
        
        # Aliases 생성 (대표 이름 제외)
        aliases = [name for name in all_names if name != p_name]
        
        # JSON 필드 처리 (port_info)
        p_info_raw = first_row.get('port_info')
        p_info = None
        if pd.notna(p_info_raw):
            try:
                if isinstance(p_info_raw, str):
                    p_info = json.loads(p_info_raw)
                else:
                    p_info = p_info_raw
            except:
                p_info = None

        port_data = {
            "port_code": p_code,
            "port_name": p_name,
            "lat": clean_float(first_row.get('lat')),
            "lng": clean_float(first_row.get('lng')),
            "nation_name": clean_str(first_row.get('nation_name')),
            "aliases": aliases if aliases else None, # 빈 리스트는 None으로 처리
            "port_info": p_info,
            "updated_at": datetime.now()
        }

        if p_code in existing_ports:
            # Update
            port = existing_ports[p_code]
            port.port_name = port_data["port_name"]
            port.lat = port_data["lat"]
            port.lng = port_data["lng"]
            port.nation_name = port_data["nation_name"]
            port.aliases = port_data["aliases"]
            port.port_info = port_data["port_info"]
            port.updated_at = datetime.now()
            updated_count += 1
        else:
            # Insert
            new_ports.append(Port(**port_data))
    
    if new_ports:
        db.add_all(new_ports)
    
    db.commit()
    print(f"Ports Loaded: {len(new_ports)} created, {updated_count} updated.")

def load_routes(db: Session, filepath: str):
    """
    tb_route.csv 파일을 읽어 TB_ROUTE 테이블에 적재
    """
    print(f"Loading Routes from {filepath}...")
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Failed to read {filepath}: {e}")
        return

    existing_routes = {r.route_idx: r for r in db.query(Route).all()}
    new_routes = []
    updated_count = 0

    for _, row in df.iterrows():
        r_idx = clean_int(row.get('route_idx'))
        if not r_idx: continue

        route_data = {
            "route_idx": r_idx,
            "svc": clean_str(row.get('svc')),
            "route_name": clean_str(row.get('route_name')),
            "region_idx": clean_int(row.get('region_idx')),
            "region": clean_str(row.get('region')),
            "sort_idx": clean_int(row.get('sort_idx')),
            "carriers": clean_str(row.get('carriers')),
            "port_rotation": clean_str(row.get('port_rotation')),
            "frequency": clean_str(row.get('frequency')),
            "duration": clean_int(row.get('duration')),
            "ships": clean_str(row.get('ships')),
            "updated_at": datetime.now()
        }

        if r_idx in existing_routes:
            # Update
            route = existing_routes[r_idx]
            for key, value in route_data.items():
                if key != "route_idx": # PK 제외
                    setattr(route, key, value)
            updated_count += 1
        else:
            # Insert
            new_routes.append(Route(**route_data))

    if new_routes:
        db.add_all(new_routes)
    
    db.commit()
    print(f"Routes Loaded: {len(new_routes)} created, {updated_count} updated.")

def load_proforma(db: Session, filepath: str):
    """
    tb_proforma.csv 파일을 읽어 TB_PROFORMA 테이블에 적재
    (Unpivot: 가로로 나열된 T1, T2... 정보를 세로로 변환)
    """
    print(f"Loading Proforma from {filepath}...")
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Failed to read {filepath}: {e}")
        return

    proforma_list = []
    
    # 처리할 route_idx 목록 (기존 데이터 삭제용)
    processed_route_idxs = set()

    for _, row in df.iterrows():
        r_idx = clean_int(row.get('route_idx'))
        if not r_idx: continue
        
        svc = clean_str(row.get('svc'))
        processed_route_idxs.add(r_idx)

        # T1, T2, T3 ... 반복 처리 (최대 3개라고 가정, 필요시 늘릴 수 있음)
        for i in range(1, 4): # 1 to 3
            t_name_col = f't{i}_name'
            t_wtp_col = f't{i}_wtp'
            t_sch_col = f't{i}_sch'
            
            t_name = clean_str(row.get(t_name_col))
            
            if t_name:
                t_wtp = clean_str(row.get(t_wtp_col))
                t_sch = clean_str(row.get(t_sch_col))

                proforma_list.append({
                    "route_idx": r_idx,
                    "svc": svc,
                    "terminal_name": t_name,
                    "wtp": t_wtp,
                    "sch": t_sch,
                    "seq": i
                })

    # 기존 데이터 삭제 (Full Refresh for affected routes)
    if processed_route_idxs:
        print(f"Clearing existing proforma for {len(processed_route_idxs)} routes...")
        db.query(Proforma).filter(Proforma.route_idx.in_(processed_route_idxs)).delete(synchronize_session=False)
        db.commit()

    # Bulk Insert
    if proforma_list:
        db.bulk_insert_mappings(Proforma, proforma_list)
        db.commit()
    
    print(f"Proforma Loaded: {len(proforma_list)} records.")


def main():
    # DB 테이블 생성
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 1. Load Ports
        if os.path.exists(FILE_PATHS["tb_port"]):
            load_ports(db, FILE_PATHS["tb_port"])
        else:
            print(f"[Warning] Port file not found: {FILE_PATHS['tb_port']}")

        # 2. Load Routes
        if os.path.exists(FILE_PATHS["tb_route"]):
            load_routes(db, FILE_PATHS["tb_route"])
        else:
            print(f"[Warning] Route file not found: {FILE_PATHS['tb_route']}")

        # 3. Load Proforma
        if os.path.exists(FILE_PATHS["tb_proforma"]):
            load_proforma(db, FILE_PATHS["tb_proforma"])
        else:
             print(f"[Warning] Proforma file not found: {FILE_PATHS['tb_proforma']}")

        print("ETL Process Completed Successfully.")

    except Exception as e:
        print(f"[Error] ETL Process Failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()