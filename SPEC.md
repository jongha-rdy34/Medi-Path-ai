# SPEC (초안 v0.1): 증상 기반 진료과·병원 안내 서비스

> 상태: **초안, 팀 검토 대기**. 아래 "열린 질문"이 정해지면 v1.0으로 확정하고, 그다음 `tasks/plan.md`와 `tasks/todo.md`를 만듭니다.
> 작성 방식: agent-skills `spec-driven-development`의 Phase 0(범위 확인)과 Phase 1(명세)

---

## 0. 가정 (틀린 게 있으면 지금 고쳐 주세요)

1. 웹 서비스로 만듭니다(모바일 웹 대응). 네이티브 앱은 만들지 않습니다.
2. 이 서비스는 **진단이 아니라 안내**입니다. 결과는 "가능성 있는 질환 Top-N + 권장 진료과 + 주변 병원"으로만 보여 줍니다.
3. 데이터 트랙 요구사항(EDA, ML 모델, 파이프라인, AI API)을 모두 포트폴리오에 담는 것을 목표로 합니다. 다만 **MVP가 먼저**이고, 파이프라인은 그 위에 붙입니다.
4. 실시간 데이터가 부족한 부분은 더미 데이터나 시뮬레이터로 채워도 됩니다(과제 안내에서 허용).
5. 코드는 하나의 GitHub 모노레포에서 관리합니다(아래 7절).

---

## 1. 목표 (Objective)

**문제**: 몸이 아플 때 "어느 과에 가야 하는지" 몰라 진료과를 잘못 찾거나, 경증인데도 응급실로 몰리거나, 반대로 위급한 신호를 놓치는 일이 생깁니다.

**사용자**: 증상이 있는 일반인과 그 보호자

**핵심 사용자 흐름**
1. 사용자가 자연어로 증상을 입력합니다. 예: "어제부터 열이 나고 오른쪽 아랫배가 아파요"
2. LLM이 증상을 구조화하고, 필요하면 추가 질문을 1~3개 합니다(발생 시점, 부위, 동반 증상 등).
3. ML 모델이 **확률이 높은 질환 Top-3와 각 확률**을 계산합니다.
4. 질환을 진료과로 매핑해 **권장 진료과**와 그 이유를 보여 줍니다.
5. 사용자 위치를 기준으로 해당 진료과가 있는 **주변 병원**을 지도와 목록으로 보여 줍니다(거리, 진료 여부 등).
6. **위급 신호**(흉통+호흡곤란, 의식 저하 등)가 감지되면 다른 결과보다 먼저 119 및 응급실 안내를 띄웁니다.

**성공 기준(측정 가능)**: 수치는 팀에서 조정합니다.
- 질환 예측 Top-3 정확도 ≥ 0.80 (홀드아웃 테스트셋 기준), 진료과 추천 정확도 ≥ 0.85
- 위급 신호 테스트 케이스 재현율(recall) 100%. 놓치는 것보다 과잉 경고가 낫습니다.
- 증상 입력부터 결과 화면까지 p95 < 5초 (LLM 호출 포함)
- 주변 병원 검색 p95 < 300ms (Elasticsearch geo 쿼리)
- `docker compose up` 한 번으로 전체 데모가 로컬에서 실행됩니다.

---

## 2. Capability Map (모듈 경계)

agent-skills 기준으로 이 요청은 독립적으로 테스트할 수 있는 기능 여러 개를 묶고 있습니다. 그래서 **모듈 지도를 먼저 합의**하고, 모듈마다 상세 스펙(`docs/specs/SPEC-<id>.md`)을 씁니다. 모듈 ID는 한 번 정하면 바꾸지 않습니다.

| Module id | 책임 | 의존 | 주 담당(안) |
|---|---|---|---|
| `api-contract` | OpenAPI 명세(요청/응답 스키마). 모든 병렬 작업의 기준점 | — | 전원 합의 |
| `data-foundation` | 증상·질환·진료과 데이터 수집, 정제, EDA, 질환→진료과 매핑 테이블 | — | 데이터 |
| `triage-model` | 증상→질환 분류 모델(베이스라인 → 파인튜닝), 추론 서비스 | `data-foundation`, `api-contract` | ML |
| `llm-assistant` | 자연어 증상 구조화, 추가 질문 생성, 결과 설명문, 위급 신호 1차 감지 | `api-contract` | AI/백엔드 |
| `hospital-search` | 병원·응급실 데이터 적재, Elasticsearch geo 검색 | `api-contract` | 데이터/백엔드 |
| `backend-api` | 위 모듈을 엮는 메인 API(세션, 오케스트레이션, 로깅) | `api-contract`, `triage-model`, `llm-assistant`, `hospital-search` | 백엔드 |
| `web-frontend` | Vue 3 UI(증상 입력/대화, 결과, 지도) | `api-contract` (개발 중에는 Mock 사용) | 프론트 |
| `data-pipeline` | Kafka/Flink/Spark/Airflow로 실시간 수집, 배치 처리, 재학습 자동화 | `data-foundation`, `hospital-search`, `triage-model` | 데이터 |
| `platform` | docker compose, CI(GitHub Actions), 환경변수와 시크릿 관리 | — | 전원 |

**빌드 순서**
```
api-contract, platform, data-foundation
   → (병렬) triage-model(베이스라인) | llm-assistant | hospital-search | web-frontend(Mock)
   → backend-api 통합 (MVP 완성)
   → triage-model(파인튜닝) | data-pipeline
```

**병렬 작업의 핵심**: `api-contract`(OpenAPI)를 1주차에 확정합니다. 그러면 프론트는 Mock 서버로, 백엔드와 ML은 계약 테스트로 서로 기다리지 않고 동시에 개발할 수 있습니다.

---

## 3. 시스템 구조 (안)

```
[Vue 3 SPA] ──REST──> [backend-api (Django + DRF)]
                          ├──> [ml-service (FastAPI)]  triage-model 추론
                          ├──> [LLM API]               llm-assistant
                          ├──> [Elasticsearch]         hospital-search (geo_point)
                          ├──> [PostgreSQL]            세션, 익명 로그, 매핑 테이블
                          └──> [Kafka] 익명화된 증상 이벤트 발행

[공공 API: 응급실 실시간 병상] ─poll─> Kafka ─> Flink ─> Elasticsearch (실시간 가용 병상)
[Kafka 증상 이벤트] ─> Flink(윈도 집계) ─> 지역별 증상 트렌드
[Airflow] ─ 매일: 병원 정보 갱신 / 매주: Spark 배치 → 재학습 → 평가 → 모델 교체
```

### 기술 스택 제안과 이유

| 영역 | 제안 | 이유 |
|---|---|---|
| 백엔드 | **Django + DRF** | ML·데이터 코드와 언어(Python)가 같아 팀 전체가 같은 언어로 리뷰할 수 있습니다. Spring을 고르면 ML 서비스와 언어가 갈립니다(열린 질문 Q3). |
| ML 서빙 | FastAPI (별도 컨테이너) | 모델 교체와 재학습을 백엔드 배포와 분리하고, ML 담당이 독립적으로 작업할 수 있습니다. |
| 프론트 | Vue 3 + Vite + TypeScript + Pinia, 지도는 Kakao Maps JS SDK | 권고 스택을 따르고, 국내 주소와 좌표에 강합니다. |
| 모델 | 베이스라인: TF-IDF/원핫 + LogisticRegression·LightGBM → 파인튜닝: 한국어 BERT 계열(KM-BERT, KLUE-RoBERTa 등) 다중 클래스 분류 | 베이스라인을 먼저 만들어야 파인튜닝 효과를 숫자로 증명할 수 있습니다. |
| LLM | Claude 또는 OpenAI API (structured output / tool use) | 증상 추출 결과를 JSON 스키마로 강제해 모델 입력과 연결합니다. |
| 검색 | Elasticsearch (geo_distance + 진료과 필터 + 한글 nori 분석기) | 과제 권고사항이고, "주변 병원" 기능에 바로 쓰입니다. |
| 파이프라인 | Kafka, Flink(PyFlink), Spark(PySpark), Airflow | 과제 권고사항입니다. 아래 5절에서 각 도구에 실제 쓰임을 붙였습니다. |
| 실험 관리 | MLflow (선택) | 재학습한 모델의 버전 관리와 비교에 씁니다. |

---

## 4. 데이터 후보 (`data-foundation`)

> 출처마다 이용 조건, 라이선스, 실제 필드를 **1주차에 확인**합니다. 아래는 후보 목록입니다.

| 용도 | 후보 | 비고 |
|---|---|---|
| 증상→질환 학습 | AI Hub 의료·헬스케어 계열 한국어 데이터(예: 헬스케어 질의응답, 의학 지식 데이터) | 한국어 자연어입니다. 신청과 승인이 필요할 수 있습니다. |
| 증상→질환 베이스라인 | Kaggle "Disease Symptom Prediction" 계열(질환 약 40종 × 증상 약 130개) | 영어 데이터입니다. 증상 사전을 번역하고 매핑해서 씁니다. |
| 질환→진료과 매핑 | 직접 구축(질병관리청·서울대병원 의학정보 등 참고) + 팀 검수 | 작은 테이블이지만 서비스 품질을 좌우합니다. |
| 병원 정보 | 건강보험심사평가원 병원정보서비스(공공데이터포털) | 진료과목, 좌표, 주소를 제공합니다. 매일 배치로 갱신합니다. |
| 실시간 데이터 | 국립중앙의료원 응급의료기관 정보 조회(실시간 가용 병상) | 실제로 실시간인 공공 데이터라서 Kafka 수집 대상으로 적합합니다. |
| 사용자 이벤트 | 서비스 로그(익명) + 시뮬레이터로 만든 더미 트래픽 | Flink 트렌드 집계에 씁니다. |

**EDA 산출물**: 질환별 클래스 불균형, 증상 빈도, 질환 간 증상 동시출현(co-occurrence) 히트맵, 진료과별 분포. 결과는 `data/notebooks/`에 둡니다.

---

## 5. 데이터 파이프라인 (`data-pipeline`, MVP 이후)

| 도구 | 실제 쓰임 |
|---|---|
| Kafka | `er-beds`(응급실 병상, 1~5분 폴링), `symptom-events`(익명 증상 이벤트) 토픽 |
| Flink | 응급실 병상 스트림을 ES에 반영하고, 지역×증상 10분 윈도로 집계합니다(유행 신호 대시보드). |
| Spark | 쌓인 로그와 데이터셋으로 배치 EDA, 학습셋 재생성, 피처를 집계합니다. |
| Airflow | DAG ① 병원 정보 일일 갱신, ② 주간 재학습(Spark → 학습 → 평가 → 기준을 넘으면 교체) |
| Elasticsearch | 병원 geo 검색, 증상 키워드 자동완성(nori) |

---

## 6. 안전·법적 경계 (필수)

- 모든 결과 화면에 "의학적 진단이 아니며, 정확한 진단은 의료진에게 받아야 한다"는 고지를 표시합니다.
- 위급 신호 규칙은 **LLM에만 맡기지 않습니다**. 규칙 기반 체크리스트를 함께 써서 둘 중 하나라도 걸리면 응급 안내를 띄웁니다.
- 건강 정보는 개인정보보호법상 민감정보입니다. 따라서 **로그인 없이 쓰고, 원문 증상은 저장하지 않으며**, 익명화한 구조화 증상과 대략적 지역(시군구 단위)만 저장합니다.
- LLM API에 개인 식별 정보를 보내지 않습니다.

---

## 7. 프로젝트 구조 & 협업 방식

**모노레포** 구조입니다. 계약(OpenAPI)과 docker compose를 한 곳에서 관리해야 병렬 작업 중 어긋남을 바로 잡을 수 있습니다.

```
symptom-care/
├── contracts/openapi.yaml      # api-contract: 변경 시 전원 리뷰
├── backend/                    # Django + DRF
├── ml-service/                 # FastAPI 추론 서버 + 학습 코드
├── frontend/                   # Vue 3 + Vite
├── data/                       # 수집 스크립트, notebooks(EDA), 매핑 테이블
├── pipeline/                   # kafka producers, flink jobs, spark jobs, airflow dags
├── infra/                      # docker-compose.yml, ES 매핑, 초기화 스크립트
├── docs/specs/                 # SPEC-<module-id>.md
├── docs/adr/                   # 아키텍처 결정 기록
└── tasks/                      # plan.md, todo.md
```

**Git 규칙** (agent-skills `git-workflow-and-versioning` 기준)
- 트렁크 기반 개발: `main`은 항상 실행 가능한 상태로 유지하고, 작업 브랜치는 1~3일 안에 머지합니다.
- 브랜치 이름: `feat/<module-id>/<짧은-설명>`. 예: `feat/hospital-search/es-geo-query`
- 커밋 메시지: Conventional Commits(`feat:`, `fix:`, `docs:`...)를 쓰고, 한 커밋에는 한 가지 논리적 변경만 담습니다.
- PR: 리뷰어 최소 1명 승인, CI 통과가 필수입니다. 경로별 담당자는 `CODEOWNERS`로 지정합니다.
- 작업 관리: GitHub Issues/Projects에 이슈 1개 = 태스크 1개로 등록하고, 라벨로 모듈 ID를 답니다.
- 시크릿(API 키)은 `.env`에만 둡니다(커밋 금지). 저장소에는 `.env.example`만 커밋합니다.

---

## 8. 명령어 (확정 후 채움)

```
전체 실행:   docker compose -f infra/docker-compose.yml up --build
백엔드 테스트: cd backend && pytest
ML 테스트:    cd ml-service && pytest
프론트:       cd frontend && npm run dev / npm run test / npm run lint
```

## 9. 테스트 전략

- 백엔드와 ML: pytest. 모델은 "고정 평가셋 Top-3 정확도 ≥ 기준"을 테스트로 고정해 성능이 떨어지는 것을 막습니다.
- 위급 신호: 케이스 테이블(입력 → 반드시 응급 안내)을 회귀 테스트로 둡니다.
- 계약 테스트: OpenAPI 스키마로 백엔드 응답을 검증합니다(schemathesis 등).
- 프론트: Vitest(컴포넌트), Playwright(핵심 흐름 E2E 1~2개).

## 10. Boundaries

- **항상**: PR 전에 테스트를 실행합니다. OpenAPI를 바꾸면 프론트와 백엔드 담당 모두에게 리뷰를 받습니다. 결과 화면에 의료 고지를 표시합니다.
- **먼저 물어보기**: DB 스키마 변경, 새 외부 의존성 추가, 모델 교체 기준 변경
- **절대 안 함**: API 키나 개인정보 커밋, 원문 증상 저장, "진단"이라는 표현 사용

---

## 11. 열린 질문 (결정 필요)

1. **팀 구성**: 몇 명이고, 각자 어떤 역할(백엔드/프론트/데이터·ML)을 맡나요? 2절의 담당 배정에 필요합니다.
2. **기간**: 마감일과 중간 발표 일정이 언제인가요? 마일스톤을 나누는 기준이 됩니다.
3. **백엔드**: Django(추천)와 Spring 중 무엇으로 할까요? 팀에 Java가 더 익숙한 사람이 많으면 Spring + Python ML 서비스 구성도 가능합니다.
4. **LLM 제공사와 예산**: Claude와 OpenAI 중 어느 쪽인가요? 누가 API 키를 발급하고 비용을 부담하나요?
5. **파인튜닝용 GPU**: Colab, 학교 서버, 클라우드 중 무엇을 쓸 수 있나요?
6. **GitHub 저장소**: 이미 만든 조직이나 저장소가 있나요? 없으면 지금 만든 로컬 저장소를 기준으로 시작합니다.
7. **배포**: 최종 데모를 로컬(docker compose)로만 할까요, 클라우드에 공개 URL까지 둘까요?
