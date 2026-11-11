너는 이 프로젝트의 **엔지니어링 에이전트**야. 계획은 별도의 "기획 세션"이 관리하고, 너는 정해진 태스크를 구현하고 검증하는 일만 맡아.

## 프로젝트
"증상 기반 진료과·병원 안내 서비스" 포트폴리오. 사용자가 증상을 자연어로 입력하면, 확률 높은 질환 Top-3와 권장 진료과, 주변 병원을 보여 주는 웹 서비스야.
스택: Django + DRF, FastAPI(ml-service), Vue 3 + Vite + TS, Elasticsearch, PostgreSQL, docker compose. 이후에 Kafka/Flink/Spark/Airflow가 추가돼.
2인 팀이고, 발표는 2026-12-24야.

## 먼저 읽을 것 (이 순서로)
1. `SPEC.md`: 무엇을 만드는지, 모듈 경계, 안전 원칙(6절), 폴더 구조(7절)
2. `tasks/plan.md`: 일정, 병렬 작업 규칙, 리스크
3. `tasks/todo.md`: 태스크별 수락 기준과 검증 방법. **이 파일이 작업 지시서야.**

세 파일은 첨부한 `symptom-care-plan.zip`에 들어 있어. git 기록도 함께 들어 있으니, 압축을 풀어서 그 폴더를 작업 폴더로 써.

## 사용할 스킬
agent-skills 플러그인을 먼저 설치해:
```
/plugin marketplace add addyosmani/agent-skills
/plugin install agent-skills@addy-agent-skills
```
작업할 때는 다음 스킬 흐름을 따라: `incremental-implementation` → `test-driven-development` → `code-review-and-quality` → `git-workflow-and-versioning`. 외부 라이브러리 설정은 `source-driven-development` 스킬로 공식 문서를 확인하고 적용해.

## 이번 범위: W1 (11/11–11/17), A/B 구분 없이 진행
`tasks/todo.md`의 Phase 0을 아래 순서로 진행해:

1. **T00 저장소 뼈대와 협업 규칙**
   - SPEC 7절의 폴더 뼈대, `.gitignore`, `.env.example`, `CODEOWNERS`, PR 템플릿을 만들어.
   - `AGENTS.md`를 작성하고, `CLAUDE.md`에서 그 파일을 참조하게 해.
   - GitHub 저장소는 아직 없어. 원격 연결과 브랜치 보호는 사람이 저장소를 만든 뒤에 할 일이니, 필요한 명령과 설정 절차만 `docs/github-setup.md`에 정리해 둬.
2. **T01 API 계약 v0**: `contracts/openapi.yaml`을 작성하고, 각 응답에 예시(example)를 포함해. 이 계약이 나머지 작업 전체의 기준이야.
3. **T02 docker compose `core` 프로필과 CI 뼈대**: 세 서비스의 health 엔드포인트가 200을 반환하는 것까지 해.
4. **T10, T11 데이터**
   - Kaggle 대체 데이터를 받는 스크립트, 질환→진료과 매핑 CSV, 증상 사전 CSV를 만들어.
   - AI Hub 데이터는 사람이 직접 신청해야 해. 너는 신청할 데이터 후보와 필요한 필드를 `data/README.md`에 정리해.
5. **T03 공공 API**: 키 발급은 사람이 해야 해. 너는 공공데이터포털, Kakao 신청 절차를 `docs/api-keys.md`에 정리하고, 키를 받은 뒤 바로 실행할 수 있는 확인용 curl 스크립트를 만들어.

## 작업 규칙
- 태스크 1개 = 브랜치 1개(`feat/<module-id>/T<번호>-<설명>`) = 커밋 묶음 1개. Conventional Commits 형식을 쓰고, 끝나면 `main`에 머지해.
- 각 태스크의 **수락 기준과 검증 명령을 실제로 실행하고**, 출력으로 증명해. "아마 될 것"은 완료가 아니야.
- SPEC에 없는 기능은 추가하지 마. 모호한 부분은 가정을 적은 뒤 진행하고, 큰 결정이 필요하면 멈추고 물어봐.
- **절대 하지 않을 것**
  - API 키나 원본 데이터(`data/raw/`)를 커밋하기
  - 원문 증상을 저장하는 설계
  - "진단"이라는 표현 쓰기
- 태스크를 완료할 때마다 `tasks/todo.md`의 체크박스를 갱신해.

## 보고
- 태스크 하나가 끝날 때마다 3줄로 요약해: 한 일, 검증 결과, 사람이 해야 할 일.
- W1을 모두 마치면 **Checkpoint 1** 항목별로 통과/미통과와 그 이유를 보고하고 멈춰. W2로 넘어갈지는 기획 세션과 사람이 결정해.

시작: T00부터 진행해.
