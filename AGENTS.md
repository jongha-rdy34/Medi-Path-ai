# AGENTS.md: AI 코딩 에이전트 작업 규칙

이 저장소에서 작업하는 모든 AI 에이전트(Claude Code 등)와 사람이 따르는 규칙입니다.
무엇을 만드는지는 `SPEC.md`, 일정은 `tasks/plan.md`, **작업 지시서는 `tasks/todo.md`** 입니다. 작업 전에 이 순서로 읽으세요.

## 1. 프로젝트 한 줄 요약
사용자가 증상을 자연어로 입력하면 가능성 높은 질환 Top-3, 권장 진료과, 주변 병원을 **안내**하는 웹 서비스입니다.
스택: Django + DRF(backend), FastAPI(ml-service), Vue 3 + Vite + TS(frontend), PostgreSQL, docker compose. 병원 검색은 Kakao 로컬 API(MVP), Elasticsearch는 4~5주차.

## 2. 모듈 경계: 자기 모듈 폴더만 수정합니다

| Module id | 폴더 | 담당 |
|---|---|---|
| `api-contract` | `contracts/` | A 작성, B 리뷰 (공동) |
| `platform` | `infra/`, `.github/`, `docs/github-setup.md`, `docs/api-keys.md` | A |
| `data-foundation` | `data/` | B |
| `triage-model` | `ml-service/` (모델·추론) | B |
| `llm-assistant` | `ml-service/llm/`, `ml-service/safety/` | B |
| `hospital-search` | `prototypes/kakao-hospital-search/`, `backend/hospitals/`, `frontend/src/features/hospitals/` (Kakao 로컬 API, T21) / `infra/elasticsearch/`(4~5주차) | **@ley-21** (hospital-search agent) |
| `backend-api` | `backend/` | A |
| `web-frontend` | `frontend/` | A |
| `data-pipeline` | `pipeline/` (kafka·flink: A / spark·airflow: B) | A + B |

- **팀원 전용 폴더(@ley-21)**: `prototypes/kakao-hospital-search/`, `backend/hospitals/`, `frontend/src/features/hospitals/`.
  **엔지니어링 agent와 hospital-search agent는 서로의 전용 폴더를 수정하지 않습니다.** 필요한 변경은 GitHub Issue로 요청합니다.
- **연결 지점**: 팀원 PR이 아래만 최소로 고칩니다. 엔지니어링 agent는 이 줄들과 충돌하지 않게 작업하고, 리뷰 요청이 오면 확인합니다.
  - `backend/config/settings.py`의 `INSTALLED_APPS` 한 줄, `backend/config/urls.py`의 `include` 한 줄
  - `.env.example`의 `KAKAO_REST_API_KEY`, `VITE_KAKAO_MAP_JS_KEY`, 이 키를 넘기는 `infra/docker-compose.yml` 환경변수
  - `docs/api-keys.md`의 Kakao 절
- **계약 변경 예고**: 팀원이 `contracts/openapi.yaml`의 `Hospital` 스키마를 Kakao 기준으로 바꿉니다(`place_id`, `category`, `place_url`, `matched_department` 추가, `has_emergency_room` null 허용). 그 PR이 머지되기 전에는 다른 사람이 `Hospital` 관련 스키마를 고치지 않습니다.
- **병원 검색 접점(W2)**: 결과 화면(T20)에는 `<HospitalFinder :department="권장 진료과 코드" />` 자리만 둡니다. 컴포넌트가 아직 없으면 같은 props의 임시 컴포넌트를 `frontend/src/features/hospitals/` **밖**에 두고 나중에 import 경로만 바꿉니다. 백엔드(T22)도 병원 검색을 직접 구현하지 않고, stub은 `backend/hospitals/` 밖에 둡니다.
- 태스크가 지정한 모듈 폴더 밖의 파일은 수정하지 않습니다. 꼭 필요하면 PR 설명에 이유를 적고 해당 담당자에게 리뷰를 받습니다.
- **공동 소유 파일**: `contracts/*`, `infra/docker-compose.yml`. 바꾸는 PR은 반드시 상대방이 리뷰합니다.
- 다른 모듈은 `contracts/`의 계약만 보고 연동합니다. 상대 모듈 내부 구현에 의존하지 않습니다.

## 3. Git 규칙
- 트렁크 기반: `main`은 항상 실행 가능한 상태입니다. 브랜치는 1~3일 안에 머지합니다.
- **태스크 1개 = 브랜치 1개 = PR 1개.** 브랜치 이름: `feat/<module-id>/T<번호>-<짧은-설명>`
  - 예: `feat/hospital-search/T21-kakao-local-search`
- 커밋: Conventional Commits(`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`). 한 커밋에는 논리적 변경 하나만 담습니다.
- PR: CI 통과 + 리뷰어 1명 승인 후 머지합니다. PR 전에 에이전트 리뷰(`/review`)를 한 번 돌립니다.
- 태스크를 끝내면 `tasks/todo.md`의 체크박스를 같은 PR에서 갱신합니다.

## 4. 절대 하지 않을 것
- **API 키·비밀값 커밋 금지.** 비밀값은 `.env`에만 두고, 키 이름만 `.env.example`에 적습니다.
- **원본 데이터 커밋 금지.** `data/raw/`는 gitignore 대상입니다. 받는 스크립트만 커밋합니다.
- **원문 증상 저장 금지.** 사용자가 입력한 문장은 DB, 파일, 로그, Kafka 어디에도 남기지 않습니다.
  저장할 수 있는 것은 익명화한 **구조화 증상(표준 증상 ID)** 과 **시군구 단위 지역**뿐입니다.
- **"진단" 표현 금지.** 결과는 "가능성 있는 질환", "권장 진료과", "안내"로 표현합니다.
  예외: 의료 고지 문구("의학적 진단이 아니며 정확한 판단은 의료진에게 받아야 합니다")
- LLM API에 개인 식별 정보(이름, 연락처, 정확한 주소·좌표 등)를 보내지 않습니다.
- 위험 요인(성 접촉 이력, 비위생적 주사 이력, 가족력)은 결정이 날 때까지 묻지도 추출하지도 않고, 모델 입력에서 항상 0으로 둡니다(SPEC 6절).
- 위급 신호 판정을 LLM에만 맡기지 않습니다. 규칙 기반 체크와 OR로 묶습니다.

## 5. 먼저 물어볼 것
DB 스키마 변경, 새 외부 의존성 추가, 모델 교체 기준 변경, `contracts/`의 하위 호환을 깨는 변경

## 6. 완료의 정의
- 태스크의 **수락 기준과 검증 명령을 실제로 실행**하고, 출력으로 증명합니다. "아마 될 것"은 완료가 아닙니다.
- 로직을 바꾸면 테스트를 먼저 씁니다(실패 확인 → 구현 → 통과).
- 외부 라이브러리 설정은 공식 문서를 확인하고, 출처 URL을 커밋 메시지나 주석에 남깁니다.
- SPEC에 없는 기능은 추가하지 않습니다. 모호하면 가정을 적고 진행하되, 큰 결정은 멈추고 묻습니다.

## 7. 명령어
```
전체 실행:     cp .env.example .env   # 최초 1회
               docker compose -f infra/docker-compose.yml --profile core up --build
               # health: http://localhost:8000/api/health, http://localhost:8001/health, http://localhost:5173/
백엔드 테스트: cd backend && pip install -r requirements-dev.txt && pytest && ruff check .
ML 테스트:     cd ml-service && pip install -r requirements-dev.txt && pytest && ruff check .
프론트:        cd frontend && npm ci && npm run dev / npm run test / npm run check:lint / npm run build
계약 검사:     npx @redocly/cli lint contracts/openapi.yaml contracts/ml-service.openapi.yaml
```
CI(`.github/workflows/ci.yml`)가 바뀐 경로별로 같은 명령을 실행합니다. 의존성은 정확한 버전으로 고정합니다.
