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
| `departments.py` | 심평원 코드 → NMC 코드 (`data/mappings/departments.csv`의 `nmc_code` 열) |
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

## 알려진 한계
- 좌표가 속한 **시군구 한 곳만** 조회해서 구 경계 근처에서는 반경 안이라도 옆 구 병원이 빠집니다.
- **공휴일은 판단하지 않습니다**(요일 기준).
- 진료시간은 기관이 **신고한 정보**라 실제와 다를 수 있습니다(응답 `notice`).
- NMC는 휴진과 정보 없음을 구분하지 않습니다. 진료시간이 하나도 없으면 `is_open_now: null`.
- 여는·닫는 시간이 같은 요일(예: 09:00~09:00)은 데이터 오류로 보고 무시합니다(24시간 진료로 읽지 않음).
- `departments.csv`에 `nmc_code` 열이 생기기 전까지는 내과(`01` → `D001`)만 진료과 조건이 걸리고, 다른 과는 진료과 조건 없이 검색됩니다(`filter_applied: false`).
- 캐시는 Django 기본(프로세스별 메모리)입니다.
