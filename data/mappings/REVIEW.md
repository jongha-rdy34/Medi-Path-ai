# 매핑 검수 체크리스트

`disease_department.csv`는 초안(`review_status=draft`)입니다. **사용자가 직접 검수**합니다.
질환 하나를 검수할 때마다 근거 URL을 `source_url`에 넣고 `review_status`를 `reviewed`로 바꾼 뒤 아래 검사를 돌리세요.

```bash
python data/scripts/check_mappings.py   # source_url이 빈 질환은 경고로 표시됩니다
```

근거로 쓸 만한 곳: 서울대학교병원 N의학정보, 국가건강정보포털(질병관리청), 대한의학회 질병 정보. 블로그나 병원 광고 페이지는 근거로 쓰지 않습니다.

## 0. 화면에서 숨길 민감 질환 목록 확정 (먼저 보세요)

`sensitive_diseases.csv`의 질환은 **사용자에게 보이는 질환 Top-3와 설명문에서 빠지고 다음 순위로 채워집니다.** 권장 진료과 점수에는 그대로 포함됩니다(모델은 다시 학습하지 않음). 숨겼다는 사실은 응답·DB·로그 어디에도 남기지 않습니다.

- 초안: `aids`(후천성면역결핍증), `hepatitis_b`, `hepatitis_c`, `hepatitis_d`
- [ ] 목록을 확정해 주세요(추가·삭제). 파일만 고치면 되고 코드는 바꾸지 않습니다.
- 처리 위치: `backend/triage/service.py`의 `build_result()` (ml-service `/predict`는 전체 확률을 그대로 돌려줌)

## 1. 판단이 갈리는 항목 (먼저 보세요)

| 질환 ID | 초안 1순위 | 대안 | 검토할 점 |
|---|---|---|---|
| `heart_attack` | 24 응급의학과 | 01 내과 | 응급 안내(T15)와 연결됩니다. 진료과 대신 "응급실"로 보여 줄지 |
| `paralysis_brain_hemorrhage` | 24 응급의학과 | 06 신경외과, 02 신경과 | 위와 같음 |
| `hypoglycemia` | 01 내과 | 24 응급의학과 | 의식 저하가 있으면 응급. 위급 신호 규칙(T15)과 맞출 것 |
| `allergy` | 13 이비인후과 | 01 내과, 14 피부과 | Kaggle 증상(재채기, 눈물, 오한) 기준으로 정했습니다. 내과(알레르기)가 더 맞는지 |
| `arthritis` | 05 정형외과 | 01 내과 | 류마티스 관절염이면 내과(류마티스)가 1순위입니다 |
| `chicken_pox` | 14 피부과 | 11 소아청소년과, 01 내과 | 환자 나이에 따라 다릅니다. 나이를 묻지 않는 지금은 무엇을 1순위로 둘지 |
| `impetigo` | 14 피부과 | 11 소아청소년과 | 위와 같음 |
| `drug_reaction` | 14 피부과 | 01 내과 | 호흡곤란을 동반하면 응급입니다(아나필락시스) |
| `cervical_spondylosis` | 05 정형외과 | 06 신경외과, 21 재활의학과 | 팔 저림 같은 신경 증상이 있으면 신경외과 |
| `bppv` | 13 이비인후과 | 02 신경과 | 일반적인 배정이지만 근거를 확인할 것 |
| `tuberculosis` | 01 내과 | 20 결핵과 | 결핵과 의원은 드물어 내과를 1순위로 했습니다 |
| `varicose_veins` | 04 외과 | 07 흉부외과 | 혈관외과는 외과 소속인 경우가 많습니다 |

## 2. 나머지 질환 (근거 URL만 채우면 됨)

- [ ] `fungal_infection` 14 피부과
- [ ] `gerd` 01 내과
- [ ] `chronic_cholestasis` 01 내과
- [ ] `peptic_ulcer` 01 내과
- [ ] `aids` 01 내과
- [ ] `diabetes` 01 내과 (대안 23)
- [ ] `gastroenteritis` 01 내과 (대안 23)
- [ ] `bronchial_asthma` 01 내과
- [ ] `hypertension` 01 내과 (대안 23)
- [ ] `migraine` 02 신경과
- [ ] `jaundice` 01 내과
- [ ] `malaria` 01 내과
- [ ] `dengue` 01 내과
- [ ] `typhoid` 01 내과
- [ ] `hepatitis_a` ~ `hepatitis_e`, `alcoholic_hepatitis` 01 내과
- [ ] `common_cold` 01 내과 (대안 23, 13)
- [ ] `pneumonia` 01 내과
- [ ] `hemorrhoids` 04 외과
- [ ] `hypothyroidism`, `hyperthyroidism` 01 내과
- [ ] `osteoarthritis` 05 정형외과 (대안 21)
- [ ] `acne`, `psoriasis` 14 피부과
- [ ] `urinary_tract_infection` 15 비뇨의학과 (대안 01)

## 3. 증상 사전(`symptoms.csv`)에서 볼 것

- [ ] 한국어 이름과 동의어가 일상 표현에 맞는지(LLM이 이 표현으로 증상 ID를 고릅니다)
- [ ] `stomach_pain`(윗배), `abdominal_pain`(복통), `belly_pain`(배꼽 주위)의 구분이 자연스러운지
- [ ] 위험 요인 3종(`extra_marital_contacts`, `receiving_unsterile_injections`, `family_history`)은 수집 보류 중입니다(SPEC 6절). 사전에는 남겨 두되 LLM이 쓰지 않습니다

## 4. 진료과 코드 표기

- `departments.csv`의 07은 출처(KR Core v1.0.2) 표기대로 "흉부외과"입니다. 현재 명칭은 "심장혈관흉부외과"이니 화면에 어떤 이름을 보여 줄지 정해 주세요.
