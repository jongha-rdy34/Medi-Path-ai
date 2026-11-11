# ml-service (triage-model)

FastAPI 추론 서버. 계약: `contracts/ml-service.openapi.yaml` (`GET /health`, `POST /predict`).

```bash
pip install -r requirements-dev.txt
python ../data/scripts/download.py        # Kaggle 원본 (저장소 루트의 data/raw/, 커밋 안 함)
python -m triage.train                    # models/baseline-2026.11.0.joblib + .metrics.json (커밋 안 함)
pytest                                    # 원본 데이터가 없으면 수락 테스트는 skip
uvicorn app.main:app --port 8001
```

- **평가(SPEC 1절)**: `Training.csv` 중복 제거 → 고유 증상 조합 단위 그룹 분할(train/val/test). `Testing.csv`는 쓰지 않습니다. 노이즈 테스트셋은 시드 고정으로 증상을 지우고 관련 없는 증상을 1개 더합니다.
- **위험 요인 3종**(`extra_marital_contacts`, `receiving_unsterile_injections`, `family_history`)은 모델 입력에서 항상 무시합니다(SPEC 6절).
- 모델이 없으면 `/health`는 200, `/predict`는 503 `model_not_loaded`입니다. compose는 `ml-service/models/`를 읽기 전용으로 마운트합니다.
- 버전 전환: `MODEL_VERSION` 환경변수(T51).

## 베이스라인 결과 (2026-11-11, seed 42)

| 평가셋 | 행 수 | Top-1 | Top-3 |
|---|---|---|---|
| 그룹 분할 테스트 | 41 | 1.000 | 1.000 |
| 노이즈 테스트 | 205 | 0.946 | 0.995 |

처음 보는 조합에서도 Top-3가 1.0입니다. 같은 질환의 조합끼리 핵심 증상을 공유하는 합성 데이터라서입니다. 의미 있는 비교 기준은 노이즈 테스트와 end-to-end(T13 이후)입니다.

## 위급 신호 규칙 (T15)

- 규칙: `safety/red_flags.yaml` (12개, 출처: 응급의료에 관한 법률 시행규칙 [별표 1]의 항목). 엔진: `safety/red_flags.py`의 `check()`
- 회귀 케이스: `safety/cases.yaml` (가상 조합 30개: 응급 25, 비응급 5). `pytest tests/test_red_flags.py`가 **응급 재현율 100%** 를 확인합니다.
- 원칙: 놓치는 것보다 과잉 경고가 낫습니다. 가슴 통증은 단독으로도 응급으로 봅니다.
- LLM 판정과 OR로 묶습니다(SPEC 6절). 백엔드 연결은 T22(stub)·T30에서 합니다.
- **검수 대기**: 법령 원문(law.go.kr)에 접근하지 못해 항목명 대조를 못 했습니다(`review_status: draft`).
