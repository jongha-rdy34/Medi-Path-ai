# MediPath (메디패스)

**증상에서 진료까지, 더 나은 의료 선택의 시작**

MediPath: AI-Powered Symptom Triage & Hospital Navigation.
증상을 자연어로 입력하면 가능성 있는 질환 Top-3, 권장 진료과, 주변 병원을 안내하는 웹 서비스입니다. (포트폴리오 프로젝트, 2인 팀)

> **의료 고지**: MediPath의 결과는 의학적 진단이 아니며 참고용 안내입니다. 정확한 진단과 치료는 의료진에게 받으세요.
> 가슴 통증, 호흡곤란, 의식 저하 같은 위급 증상이 있으면 바로 119에 전화하세요.

## 실행

```bash
cp .env.example .env
docker compose --env-file .env -f infra/docker-compose.yml --profile core up --build
```

- 프론트엔드: http://localhost:5173
- 백엔드 상태: http://localhost:8000/api/health
- ml-service 상태: http://localhost:8001/health

## 문서
- `SPEC.md`: 무엇을 만드는지, 모듈 경계, 안전 원칙
- `tasks/plan.md`, `tasks/todo.md`: 일정과 태스크
- `AGENTS.md`: 사람과 AI 에이전트가 따르는 작업 규칙
- `contracts/`: API 계약(OpenAPI)
- `data/README.md`: 데이터 출처와 처리 방식
