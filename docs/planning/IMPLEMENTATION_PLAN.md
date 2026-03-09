# RotationView: 웹 애플리케이션 개발 실행 계획

이 문서는 `PortInfoMapper` PoC(개념 증명) 프로젝트를 기반으로, 실제 사용자를 위한 대화형 선박 노선 시각화 웹 애플리케이션 **"RotationView"** 를 구축하기 위한 구체적인 실행 계획을 정의합니다.

## 1. 시스템 아키텍처

RotationView 애플리케이션은 다음과 같은 3-Tier 아키텍처를 따릅니다.

- **Frontend (Client-Side):** 사용자가 직접 상호작용하는 웹 인터페이스입니다. React와 Leaflet.js를 사용하여 동적인 지도 시각화와 사용자 경험(UX)을 제공합니다.
- **Backend (Server-Side):** 데이터 처리, 비즈니스 로직, API 제공을 담당합니다. FastAPI를 사용하여 빠르고 효율적인 RESTful API 서버를 구축합니다.
- **Database:** 모든 영구 데이터를 저장하고 관리합니다. 개발 단계에서는 SQLite로 신속하게 개발하고, 프로덕션 환경에서는 안정성과 확장성이 뛰어난 PostgreSQL을 사용합니다.

데이터 흐름은 다음과 같습니다.
`CSV/Excel 파일 -> ETL 스크립트 -> PostgreSQL DB -> Backend (FastAPI) -> Frontend (React)`

## 2. 기술 스택 (Technology Stack)

| 구분 | 기술 | 목적 및 이유 |
| :--- | :--- | :--- |
| **Frontend** | **React** (with Vite) | 컴포넌트 기반 아키텍처로 복잡한 UI를 효율적으로 구축하고 관리합니다. Vite를 사용하여 빠른 개발 서버와 최적화된 빌드를 지원합니다. |
| | **Leaflet.js** (with React-Leaflet) | 다양한 오픈소스 타일 레이어를 지원하는 경량 지도 라이브러리입니다. `react-leaflet`을 통해 React 환경에 쉽게 통합할 수 있습니다. |
| | **MUI (Material-UI)** | Google의 Material Design을 구현한 UI 라이브러리로, 완성도 높고 일관된 디자인의 UI 컴포넌트(버튼, 폼, 패널 등)를 빠르게 적용할 수 있습니다. |
| | **Axios** | 백엔드 API와 비동기 통신을 하기 위한 HTTP 클라이언트입니다. |
| **Backend** | **FastAPI** | Python 3.7+의 타입 힌트를 기반으로 한 고성능 웹 프레임워크입니다. 자동 API 문서 생성(Swagger UI), 데이터 유효성 검사 등 개발 생산성을 극대화합니다. |
| | **SQLAlchemy** | Python ORM(객체 관계 매핑) 라이브러리로, SQL 쿼리 없이 Python 코드로 데이터베이스를 조작할 수 있게 해줍니다. |
| | **Pydantic** | FastAPI의 핵심 의존성으로, 데이터 유효성 검사 및 API 입출력 스키마 정의에 사용됩니다. |
| | **Uvicorn** | FastAPI를 위한 고성능 ASGI(Asynchronous Server Gateway Interface) 서버입니다. |
| **Database** | **PostgreSQL** | 높은 안정성과 데이터 무결성을 제공하는 오픈소스 관계형 데이터베이스입니다. 향후 PostGIS 확장 기능을 통해 복잡한 지리 공간 쿼리도 지원 가능합니다. |
| | **SQLite** | 개발 초기 단계에서 별도 서버 설정 없이 파일 기반으로 빠르게 프로토타이핑하기 위해 사용합니다. |
| **Deployment**| **Docker / Docker Compose** | 개발, 테스트, 프로덕션 환경의 일관성을 보장하고, 애플리케이션(Frontend, Backend, DB)을 컨테이너화하여 배포를 단순화합니다. |
| | **Nginx** | Frontend 정적 파일 서빙 및 Backend API로의 요청을 중계하는 리버스 프록시 서버로 사용합니다. |

## 3. 데이터 모델 및 관리

API 호출 시마다 CSV를 읽는 방식은 비효율적이므로, 정형화된 데이터를 데이터베이스에 저장하고 관리하는 방식으로 전환합니다.

### 3.1. 데이터 수집 및 ETL (Extract, Transform, Load)

- **ETL 스크립트 (`scripts/etl.py`):**
  - **Extract:** `data/input` 디렉토리의 `proforma.csv`, `bpa_service_code.csv` 등 원본 CSV 파일을 Pandas로 읽어들입니다.
  - **Transform:** 기존 `module`의 로직을 재사용하여 데이터를 정제하고, `port_coordinates.csv`를 참조하여 항구 좌표를 결합합니다. 데이터 누락, 형식 오류 등을 처리합니다.
  - **Load:** SQLAlchemy를 사용하여 정제된 데이터를 SQLite 데이터베이스의 `Port`, `Route`, `Proforma` 테이블에 삽입(Insert) 또는 업데이트(Update)합니다.
- 이 스크립트는 초기 데이터 구축 및 주기적인 데이터 업데이트에 사용됩니다.

### 3.2. 데이터베이스 스키마 (`backend/app/models.py`)

SQLAlchemy를 사용하여 다음과 같이 테이블 모델을 정의합니다. 현재는 초기 개발 단계의 유연성을 위해 `port_rotation`과 같은 필드를 문자열로 저장하는 비정규화된 스키마를 사용합니다.

```python
from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Port(Base):
    __tablename__ = "ports"
    id = Column(Integer, primary_key=True, index=True)
    port_name = Column(String, unique=True, index=True, nullable=False)
    port_code = Column(String, unique=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

class Route(Base):
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True, index=True)
    service_code = Column(String, nullable=False)
    consortium = Column(String)
    port_rotation = Column(String, nullable=False) # 예: "BUS-SHA-SIN-HKG"
    direction = Column(String) # 예: "Eastbound", "Westbound"

class Proforma(Base):
    __tablename__ = "proformas"
    id = Column(Integer, primary_key=True, index=True)
    service_code = Column(String, nullable=False)
    direction = Column(String)
    port_code = Column(String, nullable=False)
    port_name = Column(String, nullable=False)
    day = Column(Integer)
    etb = Column(String) # Estimated Time of Berth
    etd = Column(String) # Estimated Time of Departure
    terminal = Column(String)
```

## 4. API 설계 (CRUD)

데이터 관리를 위해 다음과 같이 명확한 RESTful API 엔드포인트를 설계합니다. 현재 백엔드는 `Route` 및 `Port` 정보 조회에 중점을 둡니다.

| Method | Endpoint | 설명 |
| :--- | :--- | :--- |
| `GET` | `/api/routes` | 모든 노선 정보를 반환합니다. |
| `GET` | `/api/ports` | 모든 항구 목록을 반환합니다. |

## 5. 상세 실행 계획 (Phased Implementation)

### Phase 1: 기반 구축 및 백엔드 설정

1.  **프로젝트 구조 개편 (완료):**
    - 루트에 `backend`, `frontend`, `scripts` 디렉토리 생성.
    - `docker-compose.yml` 파일을 루트에 생성하여 `backend`, `postgres`, `nginx` 서비스 정의.
2.  **데이터베이스 및 ETL (완료):**
    - `backend/app/` 내에 `database.py`, `models.py`, `schemas.py` 작성 (완료).
    - `scripts/etl.py` 스크립트를 개발하여 CSV 데이터를 DB에 적재 (완료).
3.  **기본 API 구현 (완료):**
    - `backend/app/main.py`에 `/api/routes`와 `/api/ports` 엔드포인트를 구현 (완료).
    - FastAPI의 `CORSMiddleware`를 추가하여 Frontend로부터의 요청을 허용합니다.
    - `uvicorn`으로 서버를 실행하고, 브라우저나 `curl`을 통해 API 응답(JSON) 확인.

### Phase 2: 프론트엔드 시각화

1.  **React 프로젝트 설정:**
    - `frontend` 디렉토리에서 `npm create vite@latest . -- --template react` 명령어로 React 프로젝트 생성.
    - `axios`, `leaflet`, `react-leaflet`, `@mui/material` 등 의존성 설치.
2.  **핵심 컴포넌트 개발:**
    - `Map.jsx`: Leaflet 지도를 렌더링하는 컴포넌트.
    - `ServiceList.jsx`: `/api/services`를 호출하여 서비스 목록을 표시하는 컴포넌트.
    - `App.jsx`: 위 컴포넌트들을 조합하고, 서비스 선택 시 해당 노선을 Map에 그리도록 상태 관리.
3.  **API 연동 및 시각화:**
    - `ServiceList`에서 서비스를 클릭하면, `App.jsx`가 선택된 서비스 ID로 `/api/services/{service_id}`를 호출.
    - 받아온 기항지(`rotations`) 좌표를 `Map.jsx`에 전달하여 `Polyline`(항로)과 `Marker`(항구)를 지도 위에 렌더링.

### Phase 3: 고도화 및 관리자 기능

1.  **인증 시스템 도입:**
    - **(Optional)** `fastapi-users` 또는 JWT 토큰 기반의 간단한 인증 로직을 백엔드에 추가하여 관리자 전용 API를 보호.
2.  **CRUD UI 개발:**
    - 항구와 서비스를 생성/수정할 수 있는 관리자 페이지(`Admin.jsx`)를 React로 개발.
    - MUI의 `TextField`, `Button`, `DataGrid` 컴포넌트를 활용하여 폼과 데이터 테이블 구현.
    - 각 UI 이벤트를 `POST`, `PUT`, `DELETE` API와 연동.
3.  **사용자 경험 개선:**
    - 지도 위 마커 클릭 시 항구 상세 정보 팝업 표시.
    - 항로 방향(eastbound/westbound)에 따라 색상 및 화살표 데코레이터 추가.
    - 로딩 인디케이터, 에러 메시지 등 비동기 처리 상태 시각화.

### Phase 4: 배포 및 운영

1.  **Docker 최적화:**
    - Frontend는 Multi-stage build를 사용하여 최종 이미지는 Nginx 위에 빌드된 정적 파일만 포함하도록 경량화.
    - Backend는 Production용 `gunicorn`과 `uvicorn` 워커를 사용하도록 Dockerfile 수정.
2.  **Docker Compose 실행:**
    - `docker-compose up --build` 명령어로 모든 서비스(nginx, backend, db)를 프로덕션 모드로 실행.
3.  **CI/CD 파이프라인 구축:**
    - **(Optional)** GitHub Actions를 설정하여 `main` 브랜치에 Push가 발생하면 자동으로 테스트, Docker 이미지 빌드, 및 클라우드 서버(예: AWS EC2, GCP VM)에 배포되도록 자동화.
