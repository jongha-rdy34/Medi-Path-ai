# data (data-foundation)

학습 데이터 확보, 정제, 매핑 테이블, EDA를 맡는 폴더입니다. 담당: B.

```
data/
├── raw/            # 원본 데이터. gitignore 대상, 절대 커밋하지 않습니다
├── scripts/        # 받는 스크립트, 검사 스크립트(커밋 대상)
├── mappings/       # 질환→진료과, 증상 사전, 진료과 코드표(T11)
├── notebooks/      # EDA(T12)
└── tests/          # 스크립트 단위 테스트
```

## 1. 받기

```bash
pip install -r data/requirements.txt
python data/scripts/download.py
```

- 공개 Kaggle 데이터라 인증 없이 받을 수 있습니다. 인증을 요구하면 `KAGGLE_API_TOKEN`을 설정하세요([Kaggle API 설정](https://www.kaggle.com/settings/api)).
- 결과는 `data/raw/<폴더>/`에 저장되고, 파일 크기와 SHA-256이 `data/raw/MANIFEST.json`에 기록됩니다.
- 데이터셋 버전을 고정해 두었기 때문에 누가 받아도 같은 파일을 받습니다.
- 테스트: `cd data && pip install -r requirements-dev.txt && pytest`

## 2. Kaggle 대체 데이터(영어)

| 폴더 | Kaggle 핸들(고정 버전) | 파일 | 내용 |
|---|---|---|---|
| `kaggle_disease_prediction` | `kaushil268/disease-prediction-using-machine-learning/versions/1` | `Training.csv`(4,920행), `Testing.csv`(42행) | 증상 132열(원핫 0/1) + `prognosis`(질환 41종) |
| `kaggle_symptom_description` | `itachi9604/disease-symptom-description-dataset/versions/2` | `dataset.csv`, `Symptom-severity.csv`, `symptom_Description.csv`, `symptom_precaution.csv` | 같은 41종 질환. 증상별 심각도 가중치(1~7) |

**라이선스: 미확인.** Kaggle 페이지는 이 세션에서 열 수 없었고, 인증 없는 API로는 라이선스 필드를 받지 못했습니다.
사람이 두 페이지의 "License" 항목을 확인해 여기에 적어 주세요. 발표 자료에 데이터 출처를 밝힐 때도 필요합니다.
- https://www.kaggle.com/datasets/kaushil268/disease-prediction-using-machine-learning
- https://www.kaggle.com/datasets/itachi9604/disease-symptom-description-dataset

### 실제로 받아서 확인한 특성 (2026-11-11)

| 항목 | 값 | 의미 |
|---|---|---|
| 질환 수 | 41종, 질환마다 120행으로 균형 | 클래스 불균형 없음 |
| 증상 열 | 132열이지만 `fluid_overload`가 두 번 있어 고유 증상은 **131개** | 읽을 때 중복 열을 합쳐야 합니다 |
| 이름 이상 | `spotting_ urination`, `foul_smell_of urine`, `dischromic _patches`, `toxic_look_(typhos)` / 라벨 끝 공백(`'Diabetes '`, `'Hypertension '`), 오타(`Peptic ulcer diseae`, `Osteoarthristis`) | 표준 ID로 정규화합니다(T11 `symptoms.csv`, `disease_department.csv`) |
| `Training.csv` 끝 열 | 이름 없는 빈 열 1개 | 무시합니다 |
| **중복** | 4,920행 중 고유 증상 조합은 **304개뿐** | 행 대부분이 같은 조합의 반복입니다 |
| **누수** | `Testing.csv` 42행 중 **41행이 Training에 그대로 있음** | 이 테스트셋으로는 정확도가 거의 100%로 나옵니다 |
| 두 데이터셋 관계 | `itachi9604`의 질환 41종·증상 131개가 `kaushil268`과 같음 | 같은 원천으로 보입니다. 독립된 평가셋이 될 수 없습니다 |

> **평가 기준에 주는 영향(기획 세션 확인 필요)**: SPEC의 "Top-3 정확도 ≥ 0.80"을 이 데이터로 재면 거의 자동으로 통과합니다.
> 의미 있는 숫자를 얻으려면 (1) 중복을 제거한 304개 조합으로 그룹 분할하거나, (2) 증상 일부를 지운 노이즈 테스트셋을 만들거나,
> (3) T13 LLM 평가셋(한국어 증상 문장 → 증상 ID)을 거친 end-to-end 평가를 기준으로 삼는 방안이 있습니다. 결정은 T14 전에 필요합니다.

> **범위 한계**: 이 데이터에는 충수염(맹장염)이 없습니다. SPEC 1절 예시 "오른쪽 아랫배가 아파요"는 이 데이터로 학습한 모델이 맞힐 수 없습니다.
> 시연 시나리오를 데이터에 있는 질환(예: 위장염, 장티푸스)으로 바꾸거나, AI Hub 데이터로 질환 범위를 넓혀야 합니다.

## 3. AI Hub 한국어 데이터 (사람이 신청)

AI Hub(https://aihub.or.kr)는 회원가입 → 데이터셋 상세 페이지에서 "다운로드 신청" → 승인 순서입니다. 승인에 며칠 걸릴 수 있으니 **첫날 신청**합니다.
이 세션에서는 aihub.or.kr에 접근할 수 없어서, 아래 후보는 데이터셋 이름과 공개 자료로만 확인했습니다. **정확한 구성, 필드, 이용 조건은 신청 전에 상세 페이지에서 확인**하세요.

### 후보 (우선순위 순)

| 우선 | 검색어(AI Hub) | 기대하는 쓰임 | 확인할 것 |
|---|---|---|---|
| 1 | `초거대AI 헬스케어 질의응답` | 일반인의 증상 질문(한국어 자연어) → 질환/진료과 학습, T13 LLM 평가셋 문장 소재 | 질문에 질환·진료과 라벨이 붙어 있는지, 라벨 체계(질환명 목록) |
| 2 | `필수의료 의학지식` | 질환별 증상 설명 → 증상 사전 동의어, 질환→진료과 매핑 근거 | 질환 분류 체계(KCD 코드 여부), 진료과 정보 포함 여부 |
| 3 | `의료 질의응답` / `헬스케어` 키워드 전체 검색 | 위 두 개가 맞지 않을 때 대안 | 같은 항목 |

### 신청할 때 상세 페이지에서 확인할 것

| 확인 항목 | 왜 필요한가 |
|---|---|
| **안심존 여부** | AI Hub 헬스케어 데이터 일부는 "안심존(온라인/오프라인)" 보안 서버 안에서만 쓸 수 있습니다. 안심존 전용이면 Colab이나 개인 GPU로 학습할 수 없어 일정이 크게 바뀝니다. 태그를 꼭 확인하세요. |
| 반출·재배포·상업 이용 조건 | 학습한 모델을 공개 URL로 서비스해도 되는지, 데이터 샘플을 발표 자료에 실어도 되는지 |
| 파일 형식과 크기 | JSON/CSV 여부, 용량(Colab 디스크 한도) |
| 개인정보 비식별 처리 여부 | SPEC 6절. 학습 데이터에도 개인 식별 정보가 없어야 합니다 |

### 우리가 필요한 필드 (최소)

| 필드 | 설명 | 없으면 |
|---|---|---|
| 증상 텍스트 | 일반인이 쓴 한국어 증상 문장 | 이 데이터는 학습에 못 씁니다 |
| 질환 라벨 | 문장마다 질환명 또는 질환 코드(KCD) | 증상 사전 동의어 소재로만 씁니다 |
| 진료과 라벨 | 권장 진료과(있으면 매핑 검증에 사용) | 질환→진료과 매핑(T11)으로 대신합니다 |
| 분할 정보 | train/valid/test 구분 | 직접 분할합니다(질환별 층화) |

받은 데이터도 `data/raw/aihub_<이름>/`에 두고 커밋하지 않습니다. 받은 뒤 이 절에 실제 데이터셋 이름, 버전, 필드, 이용 조건을 적어 주세요.

## 4. 규칙
- `data/raw/`의 원본 파일은 커밋하지 않습니다. 매핑 CSV처럼 **직접 만든 작은 표**만 커밋합니다.
- 원본에서 만든 파생 데이터(`data/processed/`)도 커밋하지 않습니다. 만드는 스크립트를 커밋합니다.
