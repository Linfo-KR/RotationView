# RotationView: 해상 노선 시각화 플랫폼

**RotationView**는 기존 `PortInfoMapper` (또는 `SeaRoute`) 프로젝트를 확장하여, 전 세계 해상 운송 노선(Service Route)과 항구(Port), 그리고 상세 기항지 정보(Proforma Schedule)를 웹 상에서 시각적으로 탐색하고 관리할 수 있는 모던 웹 애플리케이션입니다.

기존의 CSV 데이터 처리 및 PPT 자동 생성 기능에 더해, **PostgreSQL(SQLite) 데이터베이스**, **FastAPI 백엔드**, 그리고 **React 프론트엔드(예정)** 기반의 대화형 플랫폼으로 진화했습니다.

## 📖 개요 (Overview)

- **목적:** 해상 노선 정보의 디지털 전환 및 시각화
- **핵심 기능:**
    - 노선별 기항지 순서 및 상세 스케줄 조회
    - 전 세계 항구 정보 및 좌표 관리
    - 지도 기반의 노선 시각화 (Frontend 개발 예정)
    - 관리자를 위한 데이터 CRUD API 제공

## 🏗️ 시스템 아키텍처 (Architecture)

```
[Frontend (React)] <--> [Backend (FastAPI)] <--> [Database (SQLite/PostgreSQL)]
                                      ^
                                      |
                               [ETL Script] <--> [CSV Data]
```

## 📂 프로젝트 구조 (Project Structure)

```
RotationView/
├── backend/                 # Backend API 서버 (FastAPI)
│   ├── app/
│   │   ├── main.py          # API 엔드포인트 정의
│   │   ├── models.py        # SQLAlchemy 데이터베이스 모델
│   │   ├── schemas.py       # Pydantic 데이터 스키마
│   │   └── database.py      # DB 연결 설정
│   └── requirements.txt     # Backend 의존성
├── data/                    # 데이터 저장소
│   ├── database/            # DB 적재용 정제된 CSV (Source of Truth)
│   │   ├── tb_port.csv      # 항구 정보
│   │   ├── tb_route.csv     # 노선 정보
│   │   └── tb_proforma.csv  # 기항지 상세 정보
│   └── ...
├── scripts/                 # 유틸리티 스크립트
│   └── etl.py               # CSV -> DB 데이터 적재 (ETL)
├── docs/                    # 프로젝트 문서
├── README.md                # 메인 문서
└── rotationview.db              # SQLite 데이터베이스 파일 (로컬 개발용)
```

## 💾 데이터베이스 스키마 (Database Schema)

### 1. TB_PORT (항구 정보)
전 세계 항구의 기본 정보와 좌표를 저장합니다.
- `port_code` (PK): 항구 코드 (UN/LOCODE 등)
- `port_name`: 항구 영문명
- `lat`, `lng`: 위도, 경도
- `nation_name`: 소속 국가
- `aliases`: 항구명의 이명/동의어 (JSON 배열)

### 2. TB_ROUTE (노선 정보)
선사가 운영하는 서비스 노선 정보를 저장합니다.
- `route_idx` (PK): 고유 ID
- `svc`: 서비스 코드 (예: CJ1)
- `route_name`: 노선명
- `carriers`: 운항 선사
- `port_rotation`: 전체 기항지 목록 (문자열)

### 3. TB_PROFORMA (기항지 상세)
각 노선의 기항 순서와 터미널 상세 정보를 저장합니다.
- `term_id` (PK): 고유 ID
- `route_idx` (FK): 노선 ID
- `terminal_name`: 터미널명
- `seq`: 기항 순서
- `wtp`, `sch`: 물동량 및 스케줄 정보

## 🔌 API 엔드포인트 (API Endpoints)

| Method | Endpoint | 설명 |
| :--- | :--- | :--- |
| `GET` | `/api/routes` | 모든 노선 목록 조회 (검색 가능) |
| `GET` | `/api/routes/{id}` | 특정 노선의 상세 정보 및 기항지 목록 조회 |
| `GET` | `/api/ports` | 모든 항구 목록 조회 (검색 가능) |
| `GET` | `/api/ports/{code}` | 특정 항구의 상세 정보 조회 |

*Swagger UI를 통해 API 문서를 확인하고 테스트할 수 있습니다: `http://localhost:8000/docs`*

## 🚀 시작하기 (Getting Started)

### 1. 환경 설정 (Setup)

가상 환경을 생성하고 의존성 패키지를 설치합니다.

```bash
# 가상 환경 생성 (Windows)
python -m venv .venv
.venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
pip install -r backend/requirements.txt
```

### 2. 데이터 적재 (ETL)

CSV 파일의 데이터를 데이터베이스(`rotationview.db`)에 적재합니다. 초기 실행 시 또는 데이터 업데이트 시 실행합니다.

```bash
python scripts/etl.py
```

### 3. 서버 실행 (Run Server)

백엔드 서버를 실행합니다.

```bash
uvicorn backend.app.main:app --reload --port 8000
```

서버가 실행되면 브라우저에서 `http://127.0.0.1:8000/docs` 로 접속하여 API를 테스트할 수 있습니다.

## 📝 향후 계획 (Roadmap)

- [x] DB 스키마 설계 및 구축
- [x] CSV 데이터 ETL 파이프라인 구현
- [x] FastAPI 기반 RESTful API 구현
- [ ] **React 기반 Frontend 개발**
    - [ ] Leaflet.js 지도 연동
    - [ ] 노선 검색 및 선택 UI
    - [ ] 노선 시각화 (Polyline, Marker)
- [ ] 배포 (Docker, AWS)