# 0. 기본 기획안

과거 PortInfoMapper 및 SeaRoute 였던 기본 기획안 문서

작성일 : 2025.11.12.

Update : 2025.11.12.

Update Release

[2025.11.12.] 기본 기획안 작성

Remark

[Gemini(2.5 Pro) 초안 작성]

# 🌎 프로젝트 기획안 : "RotationView" (선박 노선 시각화)

### 1. 프로젝트 개요

본 프로젝트(**"RotationView"**)의 목표는 글로벌 선박 노선(Service Lane) 정보를 수집, 관리하고 이를 웹 기반의 대화형 지도 위에 시각화하는 것입니다.

사용자는 특정 노선을 선택하여 해당 노선이 기항하는 항만(Port of Call)의 위치, 순서, 그리고 항해 방향을 한눈에 파악할 수 있습니다. 최종 산출물은 제공된 이미지(4_FE-MED)와 같이 명확한 노선도와 핵심 정보를 제공하는 웹 애플리케이션입니다.

### 2. 핵심 목표

- **데이터베이스 구축:** 항만(좌표), 선박, 노선(서비스), 터미널 정보를 효율적으로 관리할 수 있는 스키마 설계 및 DB 구축.
- **백엔드 API 개발:** 프론트엔드에 필요한 노선 데이터를 제공하는 REST API 서버를 Python으로 구축.
- **프론트엔드 시각화:**
    - 웹 지도 상에 항만 위치를 마커(Marker)로 표시.
    - 기항 순서(Rotation)에 따라 항만 간을 선(Polyline)으로 연결.
    - 항해 방향을 화살표 등으로 명확히 표시.
    - 노선명, 선박 정보, 터미널 물동량 등 부가 정보를 템플릿에 표시.

### 3. 추천 기술 스택 (Tech Stack)

요청하신 Python을 중심으로, 경량화된 최신 스택을 제안합니다.

- **백엔드 (Backend):** **Python 3.x** + **FastAPI**
    - *선정 이유:* FastAPI는 Python으로 API를 구축할 때 가장 빠르고 현대적인 프레임워크 중 하나입니다. 가볍고, 비동기 처리를 지원하며, 자동 API 문서(Swagger UI)를 생성해 주어 프론트엔드와의 연동이 매우 효율적입니다.
- **데이터베이스 (Database):** **SQLite** (개발용) / **PostgreSQL** (운영용)
    - *선정 이유:* 초기 개발 및 사이드 프로젝트에는 Python에 내장된 **SQLite**가 설정 없이 즉시 사용 가능해 가장 빠릅니다.
    - 데이터를 관리하기 위해 **SQLAlchemy** (ORM)를 사용하여 Python 코드만으로 DB를 제어합니다.
    - (확장 제안) 향후 더 복잡한 지리 정보 쿼리(e.g., "반경 100km 내 항만 찾기")가 필요하면 **PostgreSQL + PostGIS**로 마이그레이션하는 것을 권장합니다.
- **프론트엔드 (Frontend):** **HTML / CSS / JavaScript (ES6+)** + **Leaflet.js**
    - *선정 이유:* **Leaflet.js**는 오픈소스 지도 라이브러리 중 가장 가볍고 사용법이 간단합니다. 마커, 폴리라인, 팝업 등 이번 프로젝트의 핵심 기능을 모두 제공하며, React/Vue 같은 복잡한 프레임워크 없이 순수 JS(Vanilla JS)만으로도 충분히 구현 가능하여 프로젝트 복잡도를 낮춥니다.

### 4. 데이터베이스 설계 (Data Model)

효율적인 관리를 위해 다음과 같이 데이터베이스 스키마를 설계합니다. (SQLAlchemy 모델 기준)

| 테이블명 (Table) | 주요 컬럼 (Columns) | 설명 |
| --- | --- | --- |
| **Port** | `port_id` (PK), `name`, `latitude`, `longitude`, `country` | 항만 기본 정보 및 좌표 |
| **Carrier** | `carrier_id` (PK), `name` | 선사 정보 (e.g., MSC) |
| **Service** | `service_id` (PK), `name` (e.g., "Jade / MD5"), `carrier_id` (FK) | 노선(서비스) 정보 |
| **Rotation** | `rotation_id` (PK), `service_id` (FK), `port_id` (FK), `port_order`, `direction` | **핵심 데이터.** 노선의 기항 순서 (e.g., 1, 2, 3...) 및 방향 (e.g., 'eastbound') |
| **Vessel** | `vessel_id` (PK), `name`, `teu_capacity` | 선박 정보 (e.g., 23,411 teu) |
| **ServiceVessel** | (Junction Table) `service_id` (FK), `vessel_id` (FK) | 특정 노선에 투입된 선박들 (N:M 관계) |
| **TerminalInfo** | `terminal_id` (PK), `port_id` (FK), `terminal_name`, `weekly_throughput` | 항만(터미널)의 부가 정보 (e.g., PNC 물량) |

### 5. API 설계 (Endpoint Design)

FastAPI 백엔드는 프론트엔드에 데이터를 전달할 단일 엔드포인트를 제공합니다.

- **Endpoint:** `GET /api/service/{service_name}`
- **설명:** 특정 서비스(노선)의 모든 상세 정보를 JSON으로 반환합니다.
- **예시 응답 (`GET /api/service/Jade`):**

```json
{
  "service_name": "Jade",
  "alliance": "Premier Alliance (MD5 eastbound only)",
  "carriers": ["MSC"],
  "ships": {
    "count": 16,
    "capacity_teu": 23411
  },
  "rotation": [
    { "port_name": "Qingdao", "lat": 36.06, "lon": 120.38, "order": 1, "direction": "eastbound" },
    { "port_name": "Busan", "lat": 35.10, "lon": 129.04, "order": 2, "direction": "eastbound" },
    { "port_name": "Ningbo", "lat": 29.87, "lon": 121.54, "order": 3, "direction": "eastbound" },
    // ... (중략) ...
    { "port_name": "Singapore", "lat": 1.29, "lon": 103.85, "order": 10, "direction": "westbound" },
    { "port_name": "Shanghai", "lat": 31.23, "lon": 121.47, "order": 11, "direction": "westbound" }
  ],
  "terminal_info": {
    "PNC": {
      "weekly_throughput": 6700,
      "schedule": "Sun - Mon"
    }
  }
}
```

### 6. 개발 단계별 로드맵 (Phased Roadmap)

프로젝트를 4단계로 나누어 체계적으로 진행합니다.

### Phase 1: 백엔드 및 데이터 기반 구축 (Backend & Data Foundation)

1. **환경 설정:** Python 가상 환경을 설정하고 `fastapi`, `uvicorn`, `sqlalchemy`를 설치합니다.
2. **DB 모델링:** `4. 데이터베이스 설계`에 정의된 모델을 SQLAlchemy를 사용하여 `models.py`에 정의합니다.
3. **DB 초기화 및 시딩 (Seeding):**
    - SQLite 데이터베이스 파일(`rotationview.db`)을 생성합니다.
    - 제공된 이미지의 데이터('Jade' 노선, 'PNC' 터미널 정보, 항만 좌표 등)를 DB에 수동으로 입력하는 `seed.py` 스크립트를 작성하여 초기 데이터를 구축합니다.
4. **API 개발:** `5. API 설계`에 맞춰 `GET /api/service/{service_name}` 엔드포인트를 구현합니다. DB에서 데이터를 조회하여 JSON으로 반환하는 로직을 작성합니다.
5. **API 테스트:** 브라우저나 `curl`을 통해 `http://127.0.0.1:8000/api/service/Jade`를 호출하여 JSON 데이터가 정확히 출력되는지 확인합니다.

### Phase 2: 프론트엔드 시각화 (Basic Visualization)

1. **기본 HTML/JS 설정:** `index.html`, `style.css`, `app.js` 파일을 생성합니다.
2. **지도 라이브러리 연동:** `index.html`에 Leaflet.js (CDN)를 추가하고, 기본 세계 지도를 타일 레이어(예: OpenStreetMap)로 초기화합니다.
3. **API 데이터 연동:** `app.js`에서 `fetch` 함수를 사용하여 Phase 1에서 만든 백엔드 API를 호출합니다.
4. **항만 마커 표시:** API 응답의 `rotation` 배열을 순회하며, 각 항만의 `[lat, lon]` 좌표에 `L.marker()`를 사용하여 지도에 핀을 찍습니다.
5. **기본 노선 표시 (직선):** `rotation` 배열의 좌표들을 순서대로 연결하는 `L.polyline()`을 생성하여 지도에 추가합니다. (이 단계에서는 직선으로 표시됩니다.)

### Phase 3: 시각화 고급화 (Visual Enhancement)

1. **항해 방향 표시 (화살표):** 항해 방향을 명확히 하기 위해 **`Leaflet.PolylineDecorator`** 플러그인을 사용합니다. 폴리라인 위에 일정한 간격으로 화살표를 표시하여 노선의 진행 방향을 시각화합니다.
2. **방향별 노선 스타일링 (색상 구분):**
    - `rotation` 데이터의 `direction` ('eastbound', 'westbound') 값을 기준으로 데이터를 분리합니다.
    - 두 개의 `L.polyline` 객체를 생성하여, 이미지에서처럼 Eastbound(e.g., 파란색)와 Westbound(e.g., 붉은색)를 다른 색상으로 렌더링합니다.
3. **정보 표시 (UI):**
    - 항만 마커에 `bindPopup()`을 사용하여 클릭 시 항만 이름이 표시되도록 합니다.
    - `index.html`에 이미지와 유사한 정보 박스(Infor Box) 레이아웃을 만듭니다.
    - API에서 받은 `carriers`, `ships`, `terminal_info` 데이터를 이 정보 박스에 동적으로 채워 넣습니다.

### Phase 4: 확장 및 고도화 (PM 제안)

1. **해상 경로 시각화 (곡선):**
    - 현재의 직선(Polyline)은 실제 항로와 다릅니다. 실제 항로 데이터(Shapefile)를 구하는 것은 복잡하므로, 시각적인 만족도를 높이기 위해 **`Leaflet.curve`** 플러그인을 도입합니다.
    - `L.polyline` 대신 `L.curve`를 사용하여 두 항만 사이를 자연스러운 곡선으로 연결하면, 이미지와 같이 "항해"하는 느낌을 줄 수 있습니다.
2. **데이터 관리(CRUD) 기능:** 노선 정보를 `seed.py`로만 관리하는 것은 비효율적이므로, 간단한 어드민 페이지(HTML Form)를 만들어 새 노선(Service)과 기항지(Rotation)를 추가/수정/삭제하는 API 및 UI를 구현합니다.

---

### 7. 추가 제안 및 고려 사항 (PM's Note)

1. **항만 좌표 확보 (Geocoding):**
    - 기획안에서는 항만 좌표(위도/경도)가 DB에 이미 존재한다고 가정했습니다.
    - 만약 항만 *이름*만 있고 좌표가 없다면, DB 시딩(Seeding) 단계에서 **GeoPy** (Python 라이브러리) 등을 사용하여 항만 이름을 실제 좌표로 변환(Geocoding)하는 전처리 작업이 선행되어야 합니다.
2. **실제 항로 (Vessel Path) vs. 시각적 표현:**
    - 제공된 이미지의 노선(빨간/파란 선)은 육지를 우회하는 실제 항로에 가깝게 *보여줍니다*. 이는 단순히 두 점을 잇는 것이 아니라, 여러 개의 중간 경유점(Waypoint) 데이터가 있거나 복잡한 라우팅 알고리즘이 적용된 결과입니다.
    - 본 사이드 프로젝트의 범위에서는 **Phase 4**에서 제안한 **곡선(Curve) 표현**만으로도 사용자의 요구(방향성을 가진 노선도)를 90% 이상 만족시킬 수 있을 것입니다.