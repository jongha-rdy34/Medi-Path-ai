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

## 0-2. 국내에서 드문 질환 목록 확정 (`rare_in_korea.csv`) — 사용자 확정 필요

이 목록의 질환은 **화면 Top-3를 정할 때만 점수에 가중치(`RARE_DISEASE_WEIGHT`, 기본 0.3)를 곱해 순위를 낮추고**, 화면에 남으면 그 항목 아래에 짧은 안내를 붙입니다. 확률 원값과 권장 진료과 계산은 바꾸지 않습니다(민감 질환과 같은 원칙). 모델과 `/predict`도 그대로입니다.

- 초안(Kaggle 41종 중):
  | disease_id | 안내 문구 키 | 근거(요약) |
  |---|---|---|
  | `dengue` 뎅기열 | `travel` | 국내 자체 발생 없음, 해외 유입 |
  | `malaria` 말라리아 | `travel_or_border` | 휴전선 인근(인천·경기·강원 북부) 삼일열 + 해외 유입 |
  | `typhoid` 장티푸스 | `travel` | 국내 발생 적고 해외 유입 비중 큼 |
  | `hepatitis_e` E형 간염 | `travel` | 국내 발생 드묾, 해외 유입 보고 |
- 넣지 않은 것: 결핵(국내 발생이 많음), 수두·A형 간염(국내 흔함), B·C·D형 간염(민감 질환으로 이미 숨김)
- 근거는 질병관리청 감염병 포털의 법정감염병 분류입니다. 연도별 신고 건수 URL은 아직 확인하지 못했습니다(이 환경에서 접속 불가). 확정 때 `reason`에 URL을 넣어 주세요.
- 안내 문구(`backend/triage/service.py`의 `RARE_NOTES`)
  - `travel`: "국내에서는 드문 질환입니다. 최근 해외여행(특히 동남아·아프리카 등) 이력이 있다면 의료진에게 꼭 알려 주세요."
  - `travel_or_border`: "국내에서는 드문 질환입니다. 최근 해외여행이나 휴전선 인근 지역(인천·경기·강원 북부) 방문 이력이 있다면 의료진에게 꼭 알려 주세요."
- [ ] 목록과 문구를 확정해 주세요(추가·삭제는 파일만 고치면 됩니다. 새 문구 키는 코드에도 추가 필요)
- [ ] 가중치 기본값 확정(비교표: `docs/perf/rare-disease-weight.md`)

## 0-1. 심평원 ↔ NMC 진료과 코드 대응 (`departments.csv`의 `nmc_code`)

근거: `prototypes/kakao-hospital-search/nmc_department_codes.csv`(NMC 활용가이드 CODE_MST D000, 25개). 이름이 같은 것끼리 짝지었습니다.
빈칸이면 NMC에 대응 진료과가 없어 병원 검색이 진료과 조건 없이 실행됩니다(`filter_applied: false`).

이름이 달라 확인이 필요한 것(옛 명칭으로 보이는 것):

| 심평원 | NMC | 확인할 점 |
|---|---|---|
| 07 흉부외과 | D007 흉부외과 | 이름은 같지만 현재 명칭은 "심장혈관흉부외과"입니다. NMC 코드가 같은 과를 가리키는지 |
| 15 비뇨의학과 | D014 비뇨기과 | 개명 전 명칭으로 보임 |
| 17 방사선종양학과 | D019 치료방사선과 | 개명 전 명칭으로 보임 |
| 18 병리과 | D021 해부병리과 | 개명 전 명칭으로 보임 |
| 19 진단검사의학과 | D020 임상병리과 | 개명 전 명칭으로 보임 |

- 대응 없음(빈칸): 00 일반의, 20 결핵과, 25 직업환경의학과, 26 예방의학과
- NMC에만 있음: D034 구강악안면외과(우리 표에 없음, 치과 계열이라 MVP 범위 밖)
- [ ] 위 대응을 확인해 주세요. `python data/scripts/check_mappings.py`가 형식·중복·코드표 존재를 검사합니다.

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
