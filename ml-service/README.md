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
