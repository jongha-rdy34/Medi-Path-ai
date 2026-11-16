# ml-service (triage-model)

FastAPI 추론 서버. 계약: `contracts/ml-service.openapi.yaml` (`GET /health`, `POST /predict`).

```bash
pip install -r requirements-dev.txt
python ../data/scripts/download.py        # Kaggle 원본 (저장소 루트의 data/raw/, 커밋 안 함)
python -m triage.train                    # models/dropout-2026.11.0.joblib + .metrics.json (커밋 안 함)
python -m triage.train --augment none --version baseline-2026.11.0   # 이전 베이스라인
pytest                                    # 원본 데이터가 없으면 수락 테스트는 skip
uvicorn app.main:app --port 8001
```

- **평가(SPEC 1절)**: `Training.csv` 중복 제거 → 고유 증상 조합 단위 그룹 분할(train/val/test). `Testing.csv`는 쓰지 않습니다. 노이즈 테스트셋은 시드 고정으로 증상을 지우고 관련 없는 증상을 1개 더합니다.
- **위험 요인 3종**(`extra_marital_contacts`, `receiving_unsterile_injections`, `family_history`)은 모델 입력에서 항상 무시합니다(SPEC 6절).
- 모델이 없으면 `/health`는 200, `/predict`는 503 `model_not_loaded`입니다. compose는 `ml-service/models/`를 읽기 전용으로 마운트합니다.
- 버전 전환: `MODEL_VERSION` 환경변수(T51). **기본값 `dropout-2026.11.0`**(2026-11-13, 사용자 승인): 실제 입력처럼 증상 2~3개일 때 성능을 높이려고 학습 조합에서 증상 일부를 뺀 사본을 더해 학습합니다. 비교는 `docs/perf/t30-symptom-dropout.md`.
- **모델 파일 만들기와 재현성**: 모델 파일은 gitignore 대상이라 커밋하지 않습니다. 로컬·배포 서버에서 `python ../data/scripts/download.py && python -m triage.train`으로 만듭니다(compose는 `ml-service/models/`를 마운트). 분할·보강 시드(42)와 LogisticRegression `random_state=0`이 고정이라 같은 데이터에서 같은 계수가 나옵니다(테스트 `test_training_is_reproducible_with_the_same_seed`, CLI 결과와 비교 스크립트 결과의 계수 일치 확인). CI는 Kaggle 데이터를 내려받아 기본 모델을 학습하고 수락 기준(그룹·노이즈 Top-3 ≥ 0.80, 증상 2~3개 Top-3 ≥ 0.90)을 확인합니다.

## 베이스라인 결과 (2026-11-11, seed 42)

| 평가셋 | 행 수 | Top-1 | Top-3 |
|---|---|---|---|
| 그룹 분할 테스트 | 41 | 1.000 | 1.000 |
| 노이즈 테스트 | 205 | 0.946 | 0.995 |

그룹 분할 테스트의 1.000은 "정확도 100%"가 아닙니다. 같은 질환의 조합끼리 핵심 증상을 공유하는 합성 데이터라 패턴이 결정적이어서 나온 값입니다. 의미 있는 지표는 노이즈 테스트와 아래 end-to-end입니다.

### end-to-end (자연어 59문장 → LLM 추출 → 분류 모델)

```bash
python -m triage.e2e llm/eval/results/gemini-3.5-flash-lite.json   # API 추가 호출 없음
```

| LLM | 질환 Top-1 | 질환 Top-3 | 1순위 진료과 일치 |
|---|---|---|---|
| gemini-3.5-flash-lite | 0.831 | 0.932 | 0.983 |
| gemini-3.1-flash-lite | 0.831 | 0.932 | 0.983 |

위 표는 베이스라인 기준입니다. 기본 모델(`dropout-2026.11.0`)은 3.5에서 0.932 / 0.983 / 0.966, 증상 2~3개 평가 세트 Top-3 0.729 → 0.946입니다(`docs/perf/t30-symptom-dropout.md`). 1순위 진료과 일치율이 내려간 2건은 Kaggle 데이터의 증상 겹침 때문이며, 서비스 방식(Top-10 확률 합)의 진료과 일치율은 오히려 올랐습니다.

자세한 비교는 `docs/adr/0001-llm-choice.md`.

## 위급 신호 규칙 (T15)

- 규칙: `safety/red_flags.yaml` (12개, 출처: 응급의료에 관한 법률 시행규칙 [별표 1]의 항목). 엔진: `safety/red_flags.py`의 `check()`
- 회귀 케이스: `safety/cases.yaml` (가상 조합 30개: 응급 25, 비응급 5). `pytest tests/test_red_flags.py`가 **응급 재현율 100%** 를 확인합니다.
- 원칙: 놓치는 것보다 과잉 경고가 낫습니다. 가슴 통증은 단독으로도 응급으로 봅니다.
- LLM 판정과 OR로 묶습니다(SPEC 6절). 백엔드 연결은 T22(stub)·T30에서 합니다.
- **검수 대기**: 법령 원문(law.go.kr)에 접근하지 못해 항목명 대조를 못 했습니다(`review_status: draft`).
