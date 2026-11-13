# backend/hospitals — 병원 검색 (T21, @ley-21)

`GET /api/hospitals` (계약: `contracts/openapi.yaml`의 `searchHospitals`). 프로토타입(`prototypes/kakao-hospital-search/`)의 Node 서버 로직을 Django로 옮긴 앱입니다.

```
좌표 ─▶ kakao.region_of (coord2regioncode, 캐시 안 함)
      ─▶ nmc.fetch_region (NMC 병·의원 목록, 시도+시군구+진료과 단위 6시간 캐시)
      ─▶ service.search (거리, 지금 진료 중 / 야간 / 주말, 거리순, limit)
```

| 파일 | 역할 |
|---|---|
| `views.py` | 쿼리 검증(422), 오류 응답(422 `out_of_service_area`, 503 `hospital_source_unavailable`) |
| `service.py` | 검색 흐름, 하버사인 거리, 캐시, 두 단어 시군구 대체 조회 |
| `hours.py` | 진료시간 판단(한국 시간, 자정 넘김, 전날 심야 연장, 야간, 주말) |
| `nmc.py`, `kakao.py`, `http.py` | 외부 API 클라이언트(표준 라이브러리만 사용) |
| `departments.py` | 심평원 코드 → NMC 코드(`departments.csv`의 `nmc_code` 열), 이름 규칙(`name_matches`) |
| `management/commands/hospital_live_check.py` | 실제 API 확인·녹화·지연 측정(사람이 실행) |

## 설정

| 이름 | 기본값 | 설명 |
|---|---|---|
| `DATA_GO_KR_SERVICE_KEY` (env) | — | 공공데이터포털 **Decoding** 키 |
| `KAKAO_REST_API_KEY` (env) | — | Kakao REST 키(서버 전용) |
| `HOSPITALS_CACHE_SECONDS` (settings) | 21600 | NMC 결과 캐시 시간 |
| `HOSPITALS_NIGHT_CUTOFF` (settings) | `"2000"` | 평일 이 시각(HHMM) 이후까지 진료하면 야간 진료 |

## 테스트

```bash
cd backend
pytest hospitals/tests      # 실제 API를 부르지 않음(fixture + 가짜 HTTP)
```

## 실제 API 확인 (사람이 로컬에서)

저장소 루트의 `.env`에 `DATA_GO_KR_SERVICE_KEY`(Decoding 키), `KAKAO_REST_API_KEY`를 넣고 실행합니다. 키는 출력·저장되지 않고, 좌표는 고정된 공공장소만 씁니다. DB는 필요 없습니다.

```bash
cd backend
pip install -r requirements.txt
python manage.py hospital_live_check --env-file ../.env --record --measure 20
```
Windows PowerShell에서도 같은 명령입니다(`..\.env`도 됩니다).

- `[1]`: 강남역·수원 장안구·판교·세종·제주·춘천·전주에서 Kakao 시도·시군구 표기와 NMC 검색 건수
  - 두 단어 시군구(`수원시 장안구`)는 전체 이름과 앞 단어(`수원시`)를 모두 조회
  - 이름이 바뀐 도(`강원특별자치도`, `전북특별자치도`)는 새 이름과 옛 이름(`강원도`, `전라북도`)을 모두 조회
  - `open==close 요일`: 09:00~09:00처럼 여는·닫는 시간이 같은 데이터 수(서비스는 무시함)
- `--record`: 응답을 `tests/fixtures/recorded/`에 저장(커밋 전 내용 확인)
- `--measure N`: 강남역 내과·지금 진료 중으로 캐시 미스 1회, 캐시 적중 N회 지연(p50, p95)

## 실제 API 확인 결과 (2026-11-12, @ley-21 로컬)

| 지점 | Kakao 시도 / 시군구 | NMC `Q0` / `Q1` (내과 D001) |
|---|---|---|
| 강남역 | 서울특별시 / **서초구** | 서초구 290건 |
| 수원 장안구청 | 경기도 / 수원시 장안구 | `수원시 장안구` **0건**, `수원시` 506건 |
| 판교역 | 경기도 / 성남시 분당구 | `성남시 분당구` **0건**, `성남시` 463건 |
| 세종시청 | 세종특별자치시 / 없음 | `Q1` 없이 154건 |
| 제주시청 | 제주특별자치도 / 제주시 | 201건 |
| 춘천시청 | 강원특별자치도 / 춘천시 | `강원특별자치도` 116건, 옛 이름 `강원도` **0건** |
| 전주시청 | 전북특별자치도 / 전주시 완산구 | `전주시` 312건, `전주시 완산구`·옛 이름 `전라북도` **0건** |

- **두 단어 시군구는 앞 단어(시)로 조회**합니다(`service.nmc_sigungu`). 시 전체를 받아 반경으로 거릅니다.
- **새 도 이름을 그대로 씁니다.** 옛 이름 대체 조회는 필요 없습니다.
- 지연(강남역, 내과 + 지금 진료 중, 결과 184건): 캐시 미스 403 ms, 캐시 적중 20회 p50 64 ms · **p95 105 ms** (SPEC 목표 p95 < 300 ms 충족)
- 수원시 내과 506건 중 10개 요일이 `18:30~18:30`처럼 여는·닫는 시간이 같았습니다 → 무시 규칙(#14)이 실제로 필요합니다.
- 녹화 응답 일부를 `tests/fixtures/recorded/`에 줄여서 두고 `test_recorded.py`가 씁니다.

## 알려진 한계
- 좌표가 속한 **시군구 한 곳만** 조회해서 구 경계 근처에서는 반경 안이라도 옆 구 병원이 빠집니다. 실제로 강남역 좌표는 서초구로 잡혀 강남구 쪽 병원이 빠집니다.
- **공휴일은 판단하지 않습니다**(요일 기준).
- 진료시간은 기관이 **신고한 정보**라 실제와 다를 수 있습니다(응답 `notice`).
- NMC는 휴진과 정보 없음을 구분하지 않습니다. 진료시간이 하나도 없으면 `is_open_now: null`.
- 여는·닫는 시간이 같은 요일(예: 18:30~18:30)은 데이터 오류로 보고 무시합니다(24시간 진료로 읽지 않음). 다른 오타(예: 토 `18:30~13:30`)는 자정 넘김 진료로 읽힐 수 있고 걸러내지 못합니다.
- NMC의 진료과(`QD`) 조건은 "그 진료과목을 등록한 기관"이라 다른 과 의원이 섞여 나옵니다. 그래서 **의원·병원은 이름에 진료과가 들어간 곳만** 보여 줍니다(`departments.name_matches`, 동의어 포함, 종합병원은 예외). 서초구 내과 290건 → 72건(내과 의원 70 + 종합병원 2). 이름에 과를 쓰지 않는 의원(예: "OO의원")은 빠집니다.
- `departments.csv`에 `nmc_code` 열이 생기기 전까지는 내과(`01` → `D001`)만 진료과 조건이 걸리고, 다른 과는 진료과 조건 없이 검색됩니다(`filter_applied: false`).
- 캐시는 Django 기본(프로세스별 메모리)입니다.
