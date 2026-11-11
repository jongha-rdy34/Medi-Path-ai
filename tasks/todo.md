# Task List

> 형식: agent-skills `planning-and-task-breakdown`. 에이전트에게 "T21 구현해줘"처럼 번호로 지시하세요.
> 담당: **A** = 서비스 트랙(백엔드, 프론트, 검색, 배포) · **B** = 데이터·AI 트랙(데이터, 모델, LLM)
> 크기: S(1~2파일) · M(3~5파일). L 이상이면 더 쪼갭니다.

---

## Phase 0 — 기반 (W1: 11/11–11/17)

### T00 [A] 저장소와 협업 규칙 · S
GitHub 비공개 저장소를 만들고 SPEC.md와 tasks/를 올립니다. SPEC 7절의 폴더 뼈대를 만들고, AI 에이전트용 규칙 파일을 작성합니다.
- [ ] 저장소 생성, B를 collaborator로 초대, `main` 브랜치 보호(PR + 리뷰 1명 필수) · _사람 작업 대기: 절차는 `docs/github-setup.md`. Free 플랜 비공개 저장소는 브랜치 보호 불가(0단계)_
- [x] 폴더 뼈대, `.gitignore`, `.env.example`, `CODEOWNERS`, `.github/pull_request_template.md`
- [x] `AGENTS.md`(+ `CLAUDE.md`에서 참조): 모듈 경계, 브랜치·커밋 규칙, "자기 모듈 폴더만 수정", "원문 증상 저장 금지"
- [ ] 두 사람 모두 Claude Code에 agent-skills 플러그인을 설치하고, 저장소 `.claude/settings.json`에 플러그인을 등록 · _등록 완료, 각자 설치는 사람 작업(`docs/github-setup.md` 6단계)_
- **검증**: B가 clone한 뒤 테스트 PR을 올리고, 리뷰 없이는 머지가 막히는지 확인
- **의존**: 없음

### T01 [A 작성 / B 리뷰] API 계약 v0 · M
`contracts/openapi.yaml`에 MVP 엔드포인트를 정의합니다.
- `POST /api/triage/sessions` → 세션 생성
- `POST /api/triage/sessions/{id}/messages` → 증상 메시지 전송. 응답은 `추가 질문` 또는 `결과 준비됨`
- `GET /api/triage/sessions/{id}/result` → 질환 Top-3(확률), 권장 진료과, 설명, `emergency` 플래그
- `GET /api/hospitals?lat=&lng=&department=&radius=` → 주변 병원 목록
- 내부 계약 `ml-service POST /predict`: 입력은 구조화 증상, 출력은 질환·확률
- [x] 각 응답의 예시(example)를 포함합니다. Mock 서버가 이 예시를 그대로 씁니다.
- [ ] B가 `/predict` 입출력과 구조화 증상 스키마를 리뷰하고 승인 · _사람 작업 대기: `contracts/ml-service.openapi.yaml`, `openapi.yaml#/components/schemas/StructuredSymptoms`_
- **검증**: `npx @redocly/cli lint contracts/openapi.yaml` 통과
- **의존**: T00

### T02 [A] docker compose와 CI 뼈대 · M
- [x] `infra/docker-compose.yml`: `core` 프로필(frontend, backend, ml-service, postgres), `pipeline` 프로필은 자리만 확보(Elasticsearch는 2026-11-11에 `pipeline`으로 이동)
- [x] 각 서비스 Hello 수준 실행(Django health, FastAPI health, Vite 기본 페이지)
- [x] GitHub Actions: 바뀐 경로별로 lint와 테스트 실행(backend, ml-service: pytest / frontend: vitest·eslint) · _원격 저장소가 생기면 첫 실행 확인 필요_
- **검증**: `docker compose -f infra/docker-compose.yml --profile core up`을 실행하면 세 health 엔드포인트가 모두 200을 반환
- **의존**: T00

### T03 [A] 공공 API 활용신청 · S (범위 축소, 2026-11-11)
Kakao 키 발급은 팀원이 이미 했습니다(설정 절차만 문서화). 공공데이터포털 API 3개를 다룹니다.
- [x] `docs/api-keys.md`: 공공데이터포털에서 건강보험심사평가원 병원정보서비스, 국립중앙의료원 응급의료기관 정보 조회 서비스 활용신청 절차
- [x] **국립중앙의료원 전국 병·의원 찾기 서비스**(T21 MVP용) 신청 절차와 확인 스크립트 추가 (2026-11-11)
- [x] Kakao 앱 설정 절차(카카오맵 사용 설정, Web 플랫폼 도메인) 문서화
- [x] 키를 받은 뒤 바로 실행할 curl 확인 스크립트 · _`infra/scripts/check-public-apis.sh`. 요청 주소는 미검증_
- [x] 키는 `.env`에만 보관하고, 키 이름은 `.env.example`에 기록
- [ ] 활용신청과 키 발급 · _사람 작업 대기_
- **검증**: 키 발급 후 스크립트로 각 API를 1회 호출해 응답을 확인(사람이 실행)
- **의존**: 없음

### T10 [B] 학습 데이터 확보 · S (첫날 신청)
- [ ] AI Hub 의료·헬스케어 데이터를 신청합니다. 어떤 데이터셋인지, 이용 조건과 필드는 무엇인지 `data/README.md`에 기록합니다. · _후보·필요 필드·안심존 확인 항목 정리 완료(`data/README.md` 3절). 신청은 사람 작업 대기_
- [x] Kaggle Disease Symptom 계열 데이터를 내려받습니다(대체안). · _라이선스는 사람이 Kaggle 페이지에서 확인 필요_
- [x] 원본 데이터는 git에 올리지 않습니다(`data/raw/`는 gitignore). 받는 스크립트만 커밋합니다.
- **검증**: `python data/scripts/download.py` 실행 후 `data/raw/`에 파일 생성
- **의존**: 없음

### T11 [B] 질환→진료과 매핑, 증상 사전 · M
- [x] `data/mappings/disease_department.csv`: 질환, 진료과, 근거(출처 URL) · _초안(draft). 출처 URL과 팀 검수는 사람 작업 대기(`data/README.md` 4절)_
- [x] `data/mappings/symptoms.csv`: 표준 증상 ID, 한국어명, 동의어(LLM 구조화 결과가 이 ID를 씁니다)
- [x] 진료과 코드는 심평원 진료과목 코드와 맞춥니다(T21과 연결). · _`data/mappings/departments.csv`_
- **검증**: 매핑 누락 체크 스크립트 실행 시 학습 데이터의 모든 질환이 진료과를 가짐
- **의존**: T10

### ✅ Checkpoint 1 (11/17)
- [ ] 저장소, 브랜치 보호, AGENTS.md 적용
- [ ] OpenAPI v0 머지
- [ ] `compose --profile core up` 정상 동작
- [ ] 데이터와 API 키 확보(또는 대체안 확정)

---

## Phase 1 — 병렬 MVP 개발 (W2: 11/18–11/24)

### T20 [A] 프론트: 증상 대화, 결과 화면(Mock) · M
- [ ] Vue 3 + Vite + TS + Pinia, MSW로 OpenAPI 예시 응답을 사용
- [ ] 화면: 증상 입력·대화 → 결과(질환 Top-3 확률 막대, 진료과, 설명) → 병원 목록
- [ ] `emergency=true`이면 다른 내용보다 위에 119 안내 배너 표시
- [ ] 모든 결과 화면 하단에 의료 고지 문구 표시
- **검증**: `npm run test`, 모바일 폭(375px)에서 수동 확인
- **의존**: T01

### T21 [A] 공공데이터(NMC) 병원 검색 + 카카오맵 · M (팀원 담당, 2026-11-11 확정)
**담당: @ley-21** (hospital-search agent). 트래킹: GitHub Issue #1. 전용 폴더와 연결 지점은 `AGENTS.md` 2절. 엔지니어링 agent는 구현하지 않고, 리뷰와 연동만 합니다.
결정(SPEC 결정 표): 병원 데이터는 국립중앙의료원 전국 병·의원 찾기 서비스, Kakao는 지도 SDK와 좌표 → 시도·시군구 변환에만 사용.

PR 4개를 이 순서로 올립니다.
1. **[진행 중]** 프로토타입과 `nmc_department_codes.csv`(`nmc_code,name_ko`) 업로드 → `prototypes/kakao-hospital-search/` (키 제외). 프로토타입 업로드 완료(PR #2), 코드표 추가 대기
2. 계약 → `contracts/openapi.yaml`의 `Hospital`·`HospitalSearchResponse`·`/api/hospitals`를 NMC 기준으로 변경. 공동 소유라 상대 리뷰 필수
3. Django 이식 → `backend/hospitals/` 앱과 `GET /api/hospitals`(연결 지점: `INSTALLED_APPS`, `urls.py` 각 한 줄), NMC 응답 fixture 테스트
4. HospitalFinder → `frontend/src/features/hospitals/`의 `<HospitalFinder :department="..." />`(위치 권한, 위치 실패 시 지도 클릭, API 호출, 목록·카카오맵)

- [ ] 진료과 필터: 권장 진료과(심평원 코드)가 초기값, 사용자가 변경 가능. 심평원 → NMC 코드 변환은 `backend/hospitals/` 안에서만
- [ ] 지금 진료 중(KST, 자정 넘김·전날 심야 연장 포함), 야간 진료(평일 20시 이후), 주말 진료 필터. 전문의 필터·표기 없음
- [ ] 공공데이터는 시도+시군구+진료과 단위 6시간 캐시. Kakao 결과는 저장·캐시 금지, 좌표는 캐시 키에 넣지 않음
- [ ] 키: `DATA_GO_KR_SERVICE_KEY`, `KAKAO_REST_API_KEY`는 서버 전용. `VITE_KAKAO_MAP_JS_KEY`만 프론트(도메인 등록으로 보호)
- [ ] PR 3 수락 기준에 포함: **Kakao 지역 변환 결과의 시군구 표기와 NMC `Q1` 표기가 맞는지 fixture로 확인**(두 단어 시군구, 예: 수원시 장안구)
- 알려진 한계(SPEC 4.1절): 구 경계 근처 누락, 공휴일 미처리, 신고 기준 진료시간, 두 단어 시군구 형식 미확인
- **검증**: 서울 특정 좌표에서 "내과"로 검색 시 결과가 거리순으로 나오고, 세 필터가 fixture 기준 기대 건수와 일치. 캐시 적중·미적중 지연을 측정해 기록
- **의존**: T01, T02, T03(NMC 병·의원 API 키)

### T22 [A] 백엔드: 세션·오케스트레이션(stub) · M
- [ ] Django + DRF로 T01의 엔드포인트 구현. ml-service와 LLM은 stub 클라이언트로 대체
- [ ] 저장 정책: 원문 증상은 저장하지 않고, 구조화 증상과 시군구만 저장
- [ ] OpenAPI 계약 테스트(schemathesis 또는 스키마 검증)
- **검증**: `cd backend && pytest` 통과
- **의존**: T01, T02

### T12 [B] EDA 노트북 · S
- [x] 클래스 불균형, 증상 빈도, 증상 동시출현 히트맵, 진료과 분포 → `data/notebooks/eda.ipynb`
- [x] 중복 행과 고유 증상 조합 수(304개), `Testing.csv`가 `Training.csv`와 겹치는 정도(42행 중 41행)를 노트북에 보여 줍니다. 평가 방식 변경의 근거입니다
- [x] 발표용 핵심 그래프 3~5개를 `docs/figures/`에 저장 · _5개. 라벨은 영어·ID(한글 폰트 의존 없음)_
- **검증**: 노트북을 처음부터 끝까지 실행했을 때 오류 없음
- **의존**: T10, T11

### T13 [B] LLM 평가셋과 Gemini 구현 · M
- [ ] `ml-service/llm/eval/cases.jsonl`: 증상 문장 50~100개 → 정답 구조화 JSON(T11 증상 ID)과 **정답 질환 ID**. 질환 라벨은 T14의 end-to-end 평가에 씁니다
- [ ] `LLMProvider` 인터페이스(`extract_symptoms`, `next_questions`, `explain`)와 `GeminiProvider` 구현(JSON 스키마 강제)
- [ ] 평가 스크립트: 증상 추출 F1, JSON 파싱 성공률, 평균 지연, 1천 건당 비용
- [ ] 위험 요인 3종(`extra_marital_contacts`, `receiving_unsterile_injections`, `family_history`)은 묻지도 추출하지도 않음(SPEC 6절). 프롬프트와 출력 필터로 막고 테스트로 확인
- **검증**: `python -m llm.eval --provider gemini` 실행 시 결과표 출력. 그 결과를 `docs/adr/0001-llm-choice.md`에 기록
- **의존**: T01, T11

### T14 [B] 베이스라인 분류 모델 + ml-service `/predict` · M
- [x] 원핫 또는 TF-IDF + LogisticRegression/LightGBM, 학습·평가 스크립트 · _원핫 + LogisticRegression, `python -m triage.train`_
- [x] 분할: `Training.csv` 중복 제거 → 고유 증상 조합 단위 그룹 분할(train/val/test). 같은 조합이 두 셋에 겹치지 않는지 테스트로 확인. `Testing.csv`는 쓰지 않음
- [x] 위험 요인 3종은 학습·추론 입력에서 항상 0(SPEC 6절)
- [x] 노이즈 테스트셋: 시드 고정, 증상 일부 제거(dropout) + 관련 없는 증상 추가
- [ ] end-to-end 평가: T13 평가셋 문장 · _T13 이후 추가 커밋_ — → LLM 구조화 → `/predict` Top-3 정확도와 진료과 추천 정확도
- [x] FastAPI `/predict`(T01 계약), 모델 파일은 버전 이름으로 저장 · _계약 스키마로 응답 검증하는 테스트 포함_
- **검증**: `cd ml-service && pytest`. 그룹 분할 테스트셋과 노이즈 테스트셋 모두 Top-3 ≥ 0.80. end-to-end 지표를 기록(이후 T50의 비교 기준)
- **의존**: T01, T10, T11 (end-to-end 평가는 T13)

### T15 [B] 위급 신호 규칙과 회귀 테스트 · S
- [x] `ml-service/safety/red_flags.yaml`: 규칙(증상 조합 → 응급) 과 출처 · _12개, 법령 [별표 1] 항목. 원문 대조는 사람 검수 대기_
- [x] 케이스 테이블 테스트. 위급 케이스는 반드시 `emergency=true` · _응급 25/25, 비응급 5/5_
- **검증**: 위급 케이스 재현율 100%로 테스트 통과
- **의존**: T11

---

## Phase 2 — 통합과 첫 배포 (W3: 11/25–12/01)

### T30 [A] 실제 연동과 지도 · M
- [ ] 백엔드의 stub을 실제 ml-service, LLMProvider, Kakao 병원 검색으로 교체. 위급 판정은 규칙 OR LLM
- [ ] 프론트의 Mock을 끄고 실제 API에 연결, 카카오맵에 병원 마커 표시, 브라우저 위치 권한(거부 시 주소 입력)
- **검증**: "열이 나고 기침과 가래가 나와요"를 입력하면 결과(폐렴 가능성), 진료과(내과·호흡기), 병원 목록·지도까지 전부 뜨고 p95 < 5s. "가슴이 아프고 식은땀이 나요"를 입력하면 응급 안내(119)가 결과보다 먼저 뜸. Playwright E2E 1개 통과
- **의존**: T13, T14, T15, T20, T21, T22

### T31 [A] 클라우드 배포 + 가이드 · M
- [ ] 클라우드 후보(GCP 크레딧, AWS 프리티어, Oracle Free ARM)를 비교해 결정 → `docs/adr/0002-hosting.md`
- [ ] VM에 docker compose `core` 프로필을 올리고, Caddy로 HTTPS, 도메인 연결
- [ ] `docs/deploy.md`: 처음 쓰는 사람도 따라 할 수 있는 단계별 가이드(VM 생성, 방화벽, 도커 설치, 배포, 업데이트)
- [ ] (선택) GitHub Actions로 `main` 머지 시 자동 배포
- **검증**: 휴대폰 LTE에서 공개 URL로 접속해 전체 흐름이 동작
- **의존**: T02, T30

### ✅ Checkpoint 2 (12/1): MVP 공개
- [ ] 공개 URL에서 증상 입력부터 결과, 병원 지도까지 동작
- [ ] 위급 신호 테스트 100%, CI 통과
- [ ] 이 시점 상태를 `v0.1.0`으로 태그(발표 백업용)

---

## Phase 3 — 데이터 트랙 고도화 (W4–W5: 12/02–12/15)

### T50 [B] 한국어 BERT 파인튜닝 · M
- [ ] KLUE-RoBERTa-base 또는 KM-BERT로 증상→질환 분류 학습(Colab, 5060, 3080 Ti 중 하나)
- [ ] RTX 5060을 쓰면 `cu128` PyTorch에서 `torch.cuda.is_available()`부터 확인
- [ ] 베이스라인(T14)과 Top-1·Top-3 정확도, 추론 지연(CPU)을 비교하는 표
- **검증**: 그룹 분할 테스트셋과 노이즈 테스트셋 모두 Top-3 ≥ 0.80이고 베이스라인보다 높음. end-to-end 지표도 베이스라인과 비교. CPU 추론 p95 < 300ms
- **의존**: T14

### T51 [B] ml-service 모델 교체 · S
- [ ] 환경변수 `MODEL_VERSION`으로 베이스라인과 BERT를 전환, 기본값은 성능이 좋은 쪽
- **검증**: 계약 테스트 통과, 배포 환경에서 동작
- **의존**: T50, T31

### T52 [B] (확장) 소형 LLM QLoRA 실험 · M
- [ ] Qwen2.5-3B 또는 Gemma 3~4B급 모델을 QLoRA로 학습(3080 Ti 12GB). 학습 데이터는 T13 형식
- [ ] `LocalProvider` 구현, 같은 평가셋으로 Gemini와 비교 → ADR 0001 갱신
- **검증**: 비교표(F1, 파싱 성공률, 지연, 비용)
- **의존**: T13

### T53 [B] Spark 배치 + Airflow 재학습 DAG · M
- [ ] `pipeline/spark/build_training_set.py`: 원본 데이터 + 익명 로그 → 학습셋
- [ ] `pipeline/airflow/dags/retrain_weekly.py`: Spark → 학습 → 평가 → 기준 초과 시 모델 교체
- **검증**: `pipeline` 프로필에서 DAG를 수동 실행해 성공, 새 모델 버전 파일이 생성됨
- **의존**: T50, T61

### T60 [A] Kafka·Flink 응급실 실시간 병상 + 심평원·ES 병원 검색 · M
(2026-11-11: MVP 병원 검색이 NMC 공공데이터로 확정됐지만, 이 태스크의 심평원 적재·ES·응급실 병상은 그대로 4~5주차입니다.)
- [ ] 심평원 병원정보 적재 스크립트(진료과 코드, 좌표 포함), ES 인덱스 매핑(`geo_point`, nori), 진료과 필터 + `geo_distance` 쿼리 (기존 T21에서 이동)
- [ ] ES를 compose `pipeline` 프로필에서 켬
- [ ] Producer: 국립중앙의료원 API를 1~5분마다 폴링해 Kafka `er-beds` 토픽으로 보냄
- [ ] Flink(PyFlink) 잡: 정제 후 ES 병원 문서의 `er_available_beds` 필드 갱신
- [ ] 프론트 병원 목록에 응급실 가용 병상과 갱신 시각 표시
- **검증**: `pipeline` 프로필 실행 5분 안에 ES 값이 바뀌고 화면에 반영됨
- **의존**: T03, T21, T30

### T61 [A] 증상 이벤트 스트림과 트렌드 대시보드 · M
- [ ] 백엔드가 익명 증상 이벤트를 Kafka `symptom-events`로 발행
- [ ] 더미 트래픽 시뮬레이터(지역별 증상 분포)
- [ ] Flink 10분 윈도 집계 → ES → 프론트 "지역별 증상 트렌드" 페이지
- **검증**: 시뮬레이터를 돌리면 대시보드 수치가 갱신됨
- **의존**: T30

### T62 [A] Airflow 병원정보 일일 갱신 DAG · S
- [ ] T60의 심평원 적재 스크립트를 매일 실행하는 DAG
- **검증**: DAG를 수동 실행해 성공, 문서 수와 갱신 시각 로그 확인
- **의존**: T60, T53(Airflow 설치)

### ✅ Checkpoint 3 (12/15)
- [ ] 파인튜닝 모델이 서비스에 적용되고 비교표 작성 완료
- [ ] Kafka, Flink, Spark, Airflow, ES를 각각 시연할 수 있음
- [ ] 공개 URL 정상 동작

---

## Phase 4 — 마무리 (W6: 12/16–12/24)

### T70 [A+B] 기능 동결과 안정화 · S
- [ ] **12/19 기능 동결**: 이후에는 버그 수정만 합니다.
- [ ] E2E 테스트 통과, 공개 URL 점검, `v1.0.0` 태그
- **의존**: CP3

### T71 [A] 문서 · S
- [ ] README(소개, 아키텍처 다이어그램, 실행 방법, 스크린샷), ADR 정리
- **의존**: T70

### T72 [B] 발표자료와 시연 · S
- [ ] 발표 흐름: 문제 → 데이터·EDA → 모델(베이스라인 대비 파인튜닝) → 서비스 시연 → 파이프라인 → 한계와 안전장치
- [ ] **시연 백업 영상** 녹화(네트워크 장애 대비)
- **의존**: T70
