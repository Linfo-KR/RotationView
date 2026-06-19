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
    result = m.calculate_route_geometry(db, "Port Klang,Haiphong,Yantian,Ningbo,Shanghai,Busan,Yokohama,Norfolk,Savannah,Charleston,Miami,Port Klang")
    print("outbound segments:", len(result['outbound']))
    print("inbound segments:", len(result['inbound']))
    for i, seg in enumerate(result['outbound']):
        print(f"  outbound[{i}] pts={len(seg)}, first={seg[0]}, last={seg[-1]}")
    for i, seg in enumerate(result['inbound']):
        print(f"  inbound[{i}] pts={len(seg)}, first={seg[0]}, last={seg[-1]}")
finally:
    db.close()
