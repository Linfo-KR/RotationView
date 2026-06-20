"""
CBX 노선의 geometry를 직접 계산하여 Outbound/Inbound 분리가 올바른지 확인.
"""
import sys
sys.path.insert(0, '.')
import os
os.chdir(r'c:\dev\src\RotationView\backend')

# 직접 DB 연결해서 테스트
from app.database import SessionLocal
from app import main as m

db = SessionLocal()
try:
    print("=== Test 1: CBX Route ===")
    result = m.calculate_route_geometry(db, "Port Klang,Haiphong,Yantian,Ningbo,Shanghai,Busan,Yokohama,Norfolk,Savannah,Charleston,Miami,Port Klang")
    print("outbound segments:", len(result['outbound']))
    print("inbound segments:", len(result['inbound']))
    print("segment_distances:", result.get('segment_distances'))
    
    print("\n=== Test 2: India bypass (Jebel Ali -> Tanjung Pelepas) ===")
    result_india = m.calculate_route_geometry(db, "Jebel Ali,Tanjung Pelepas,Jebel Ali")
    print("outbound segments:", len(result_india['outbound']))
    print("inbound segments:", len(result_india['inbound']))
    print("total distance (km):", result_india.get('total_distance_km'))
    print("segment_distances:", result_india.get('segment_distances'))
finally:
    db.close()
