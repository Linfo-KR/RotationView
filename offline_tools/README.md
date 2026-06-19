# Offline Tools & Macros

이 폴더는 웹 서비스(백엔드 및 프론트엔드) 구동 시 직접적으로 사용되지 않는 **데이터 파이프라인(ETL), 매크로 스크립트 도구들**이 모여있는 공간입니다. 

* `main.py`: 이전에 프로젝트 루트에 있던 매크로용 진입점 스크립트입니다. 웹 서비스에서는 FastAPI 진입점인 `backend/app/main.py`와 React 렌더링 진입점이 사용되므로, 이 파일은 서비스 구동에 **필요하지 않습니다.** (PPT 자동화, CSV 산출 등 로컬 단발성 작업을 위해 이곳으로 격리되었습니다)
* `module/` & `config/` & `data/`: `main.py`에서 파생되는 PPT 자동화 및 초기 데이터 전처리를 담당했던 관련 파일 모음입니다.
* `scripts/`: 추가적인 ETL 파이프라인이나 DB 마이그레이션 스크립트 작업이 필요할 경우 이곳에 작성/보관됩니다.
* `requirements.txt`: 위 스크립트 실행에 필요한 Pandas, python-pptx 등의 데이터 수집·가공 라이브러리 의존성 명세입니다. 백엔드 구성 시에는 서버 경량화를 위해 `backend/requirements.txt`만 사용됩니다.
