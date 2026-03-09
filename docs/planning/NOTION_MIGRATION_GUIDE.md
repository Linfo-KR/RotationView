# 마크다운 문서를 Notion으로 옮기는 방법

이 가이드는 `IMPLEMENTATION_PLAN.md` 문서를 Notion의 기능을 최대한 활용하여 효과적으로 재구성하는 방법을 안내합니다. 아래 구조를 참고하여 Notion 페이지를 만들어보세요.

---

## 🚀 RotationView: 웹 애플리케이션 개발 계획

*(<- 이 부분을 Notion 페이지의 제목으로 사용하세요)*

### 📖 개요

> 이 문서는 `PortInfoMapper` PoC(개념 증명) 프로젝트를 기반으로, 실제 사용자를 위한 대화형 선박 노선 시각화 웹 애플리케이션 **"RotationView"** 를 구축하기 위한 구체적인 실행 계획을 정의합니다.

---

### 🏛️ 시스템 아키텍처

*(<- 이 섹션은 '토글 목록' 또는 '토글 제목' 블록으로 만들어 보세요. 단축키: `>` + `space`)*

- **Frontend (Client-Side):** 사용자가 직접 상호작용하는 웹 인터페이스입니다. React와 Leaflet.js를 사용하여 동적인 지도 시각화와 사용자 경험(UX)을 제공합니다.
- **Backend (Server-Side):** 데이터 처리, 비즈니스 로직, API 제공을 담당합니다. FastAPI를 사용하여 빠르고 효율적인 RESTful API 서버를 구축합니다.
- **Database:** 모든 영구 데이터를 저장하고 관리합니다. 개발 단계에서는 SQLite로 신속하게 개발하고, 프로덕션 환경에서는 안정성과 확장성이 뛰어난 PostgreSQL을 사용합니다.

**데이터 흐름:**
`CSV/Excel 파일` → `ETL 스크립트` → `PostgreSQL DB` → `Backend (FastAPI)` → `Frontend (React)`

---

### 🛠️ 기술 스택 (Technology Stack)

*(<- 이 부분은 Notion에서 `/database - 인라인` 명령어로 '데이터베이스'를 생성하세요.)*

**데이터베이스 속성 추천:**
- **구분** (선택 속성: `Frontend`, `Backend`, `Database`, `Deployment`)
- **기술** (제목 속성)
- **목적 및 이유** (텍스트 속성)

**데이터베이스 내용:**

| 구분 | 기술 | 목적 및 이유 |
| :--- | :--- | :--- |
| Frontend | React (with Vite) | 컴포넌트 기반 아키텍처로 복잡한 UI를 효율적으로 구축하고 관리합니다. Vite를 사용하여 빠른 개발 서버와 최적화된 빌드를 지원합니다. |
| Frontend | Leaflet.js (with React-Leaflet) | 다양한 오픈소스 타일 레이어를 지원하는 경량 지도 라이브러리입니다. `react-leaflet`을 통해 React 환경에 쉽게 통합할 수 있습니다. |
| Frontend | MUI (Material-UI) | Google의 Material Design을 구현한 UI 라이브러리로, 완성도 높고 일관된 디자인의 UI 컴포넌트(버튼, 폼, 패널 등)를 빠르게 적용할 수 있습니다. |
| Backend | FastAPI | Python 3.7+의 타입 힌트를 기반으로 한 고성능 웹 프레임워크입니다. 자동 API 문서 생성(Swagger UI), 데이터 유효성 검사 등 개발 생산성을 극대화합니다. |
| ... | ... | ... |

---

### 🗃️ 데이터 모델 및 관리

*(<- '토글 제목' 블록으로 만들어 보세요)*

#### 데이터 수집 및 ETL (Extract, Transform, Load)
- **ETL 스크립트 (`scripts/etl.py`):**
  - **Extract:** `data/input` 디렉토리의 `proforma.csv`, `bpa_service_code.csv` 등 원본 CSV 파일을 Pandas로 읽어들입니다.
  - **Transform:** 기존 `module`의 로직을 재사용하여 데이터를 정제하고, `port_coordinates.csv`를 참조하여 항구 좌표를 결합합니다. 데이터 누락, 형식 오류 등을 처리합니다.
  - **Load:** SQLAlchemy를 사용하여 정제된 데이터를 PostgreSQL 데이터베이스의 `ports`, `services`, `rotations` 테이블에 삽입(Insert) 또는 업데이트(Update)합니다.

#### 데이터베이스 스키마 (`backend/app/models.py`)
*(<- 아래 내용은 `/code` 명령어로 '코드 블록'을 만들고, 언어를 'Python'으로 설정한 뒤 붙여넣으세요.)*
```python
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class Port(Base):
    __tablename__ = "ports"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    code = Column(String, unique=True, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)

# ... (이하 전체 모델 코드)
```

---

### 📡 API 설계 (CRUD)

*(<- 이 부분도 '데이터베이스'로 만들고, '상태' 속성을 추가하여 진행 상황을 추적해 보세요.)*

**데이터베이스 속성 추천:**
- **Method** (선택 속성: `GET`, `POST`, `PUT`, `DELETE`)
- **Endpoint** (제목 속성)
- **설명** (텍스트 속성)
- **상태** (선택 속성: `계획`, `진행중`, `완료`)

| Method | Endpoint | 설명 | 상태 |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/services` | 모든 서비스(항로) 목록을 반환합니다. | 계획 |
| `GET` | `/api/services/{service_id}` | 특정 서비스의 상세 정보와 전체 기항지(`rotations`) 정보를 반환합니다. | 계획 |
| ... | ... | ... | ... |

---

### 🗺️ 상세 실행 계획 (Phased Implementation)

*(<- 이 섹션은 '데이터베이스'로 만들고, '보드 보기'를 추가하여 칸반 보드로 활용하세요.)*

**데이터베이스 속성 추천:**
- **작업명** (제목 속성)
- **Phase** (선택 속성: `Phase 1`, `Phase 2`, `Phase 3`, `Phase 4`)
- **상태** (선택 속성: `To Do`, `In Progress`, `Done`)
- **담당자** (사용자 속성)
- **마감일** (날짜 속성)

**보드 보기 설정:**
- 그룹화 기준: `Phase` 속성

**데이터베이스 내용 (일부):**

| 작업명 | Phase | 상태 |
| :--- | :--- | :--- |
| 프로젝트 구조 개편 | Phase 1 | To Do |
| 데이터베이스 및 ETL | Phase 1 | To Do |
| 기본 API 구현 | Phase 1 | To Do |
| React 프로젝트 설정 | Phase 2 | To Do |
| 핵심 컴포넌트 개발 | Phase 2 | To Do |
| ... | ... | ... |
