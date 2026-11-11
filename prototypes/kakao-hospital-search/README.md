# kakao-hospital-search (T21 프로토타입, 참고용)

내 위치 주변에서 **진료과 + 지금 진료 중 / 야간 / 주말** 조건에 맞는 병원을 가까운 순으로 찾아 카카오맵에 보여 주는 프로토타입입니다.
T21에서 이 로직을 Django `backend/hospitals/`와 Vue `frontend/src/features/hospitals/`로 옮깁니다. 이 폴더는 이식이 끝나면 지웁니다(`prototypes/README.md` 규칙). CI 대상이 아닙니다.

- 병원 데이터: **국립중앙의료원 전국 병·의원 찾기 서비스**(공공데이터포털)
- 지도: **Kakao Maps JavaScript SDK**(지도, 마커, 좌표 → 시도·시군구 변환)
- 서버: Node.js(Express) 중계 서버. 공공데이터 API가 XML만 주고 CORS를 지원하지 않으며, 인증키를 브라우저에 노출하면 안 되기 때문에 둡니다.

```
kakao-hospital-search/
├── server.js          # 공공데이터 호출, 조건 필터, 6시간 캐시
├── public/index.html  # 카카오 지도 + 필터 UI + 결과 목록
├── package.json
└── .env.example
```

## 실행 방법

필요한 것: Node.js 18 이상(내장 `fetch` 사용)

1. `.env.example`을 `.env`로 복사하고 키를 넣습니다.
2. `public/index.html`의 `YOUR_JS_KEY`를 Kakao JavaScript 키로 바꿉니다(커밋하지 마세요).
3. Kakao Developers 콘솔에서 JavaScript SDK 도메인(Web 플랫폼 사이트 도메인)에 `http://localhost:3000`을 등록합니다.
4. 아래 명령을 실행하고 `http://localhost:3000`을 엽니다. 파일을 더블클릭(`file://`)으로 열면 도메인 인증이 안 돼서 동작하지 않습니다.

```bash
npm install
npm start
```

PC는 위치가 잘 안 잡힙니다. **지도를 클릭하면 그 지점을 내 위치로 지정**해서 검색할 수 있습니다.

## 필요한 키

| 키 | 넣는 곳 | 비고 |
|---|---|---|
| 공공데이터포털 일반 인증키 **(Decoding)** | `.env`의 `DATA_GO_KR_SERVICE_KEY` | 포털에서 "국립중앙의료원_전국 병·의원 찾기 서비스" 활용신청 승인 필요. Encoding 키를 넣으면 이중 인코딩되어 `SERVICE_KEY_IS_NOT_REGISTERED` 오류 |
| Kakao JavaScript 키 | `public/index.html`의 `YOUR_JS_KEY` | 콘솔에서 카카오맵 [사용 설정] ON, 사이트 도메인 등록 필요 |

프로토타입은 좌표 → 시도·시군구 변환을 브라우저의 Kakao SDK(`services.Geocoder.coord2RegionCode`)로 합니다. Django로 옮길 때는 인계장 v2에 따라 서버에서 Kakao REST `coord2regioncode`(`KAKAO_REST_API_KEY`)로 바꿉니다.

## 동작 흐름

1. 브라우저에서 현재 위치를 얻습니다(실패하면 지도 클릭으로 지정).
2. Kakao Geocoder로 좌표를 시도·시군구로 바꿉니다. 예: `서울특별시` / `강남구`
3. `GET /api/hospitals?lat&lng&radius&sido&sigungu&dept&openNow&night&weekend`
4. 서버가 해당 시군구(+진료과)의 병원 전체를 공공데이터 API에서 페이지를 반복해 받아옵니다. 시도+시군구+진료과 단위로 6시간 캐시합니다(공공데이터라 저장 허용).
5. 서버가 거리(하버사인)와 조건으로 거르고 가까운 순으로 최대 100건을 돌려줍니다.

## 사용하는 외부 API와 필드

### 국립중앙의료원 전국 병·의원 찾기 서비스
- `GET https://apis.data.go.kr/B552657/HsptlAsembySearchService/getHsptlMdcncListInfoInqire` (응답 XML)

| 요청 파라미터 | 의미 | 예 |
|---|---|---|
| `serviceKey` | 인증키(Decoding) | |
| `Q0` / `Q1` | 시도 / 시군구 | `서울특별시` / `강남구` |
| `QD` | 진료과목 코드(NMC 코드) | `D001` 내과, `D002` 소아청소년과 |
| `QT` | 진료요일(프로토타입은 미사용) | 1~7 월~일, 8 공휴일 |
| `pageNo`, `numOfRows` | 페이지 | `numOfRows=1000` |

| 응답 필드 | 의미 |
|---|---|
| `hpid` | 기관 ID |
| `dutyName`, `dutyAddr`, `dutyTel1` | 기관명, 주소, 대표전화 |
| `dutyDivNam` | 기관 구분(의원, 병원 등) |
| `wgs84Lat`, `wgs84Lon` | 좌표 |
| `dutyTime1s`~`dutyTime8s` / `dutyTime1c`~`dutyTime8c` | 요일별 진료 시작 / 종료(`HHMM`). 1~7 월~일, 8 공휴일 |

- 위치(반경) 검색 기능이 없어서 시도·시군구 단위로 받아 서버에서 거리를 계산합니다.
- 응답에 진료과목 필드가 없습니다. 진료과는 요청의 `QD`로만 거를 수 있습니다.
- 진료과목 코드 전체 표(CODE_MST `D000`, D001~D029)는 활용가이드에서 옮겨 `nmc_department_codes.csv`로 추가할 예정입니다. 서비스 전체는 심평원 코드(`data/mappings/departments.csv`)를 쓰고, NMC 코드로 바꾸는 일은 서버 안에서만 합니다.

### Kakao Maps JavaScript SDK
- `sdk.js?appkey=...&libraries=services&autoload=false`
- `kakao.maps.Map`, `Marker`, `Circle`, `InfoWindow`
- `services.Geocoder.coord2RegionCode(lng, lat)` → `region_type`이 `B`(법정동)인 항목의 `region_1depth_name`(시도), `region_2depth_name`(시군구)

## 조건 판단 기준

| 조건 | 판단 |
|---|---|
| 지금 진료 중 | 오늘 요일의 진료시간과 현재 **한국 시간**(`Asia/Seoul`)을 비교. 자정을 넘기는 진료(예: 19:00~02:00)와, 전날 심야진료가 새벽까지 이어지는 경우도 처리 |
| 야간 진료 | 평일(월~금) 중 하루라도 **20:00 이후**까지 진료. `server.js`의 `NIGHT_CUTOFF` |
| 주말 진료 | 토 또는 일 진료시간이 등록되어 있음 |

## 알려진 한계
- 시군구 단위로 조회하므로 **구 경계 근처에서는 반경 안에 있어도 옆 구 병원이 빠질 수 있습니다.**
- **공휴일은 따로 처리하지 않습니다**(평소 요일 기준으로 판단).
- 진료시간은 기관이 신고한 정보라서 **실제와 다를 수 있습니다.** 서비스에서는 방문 전 전화 확인 안내를 함께 보여 줍니다.
- 진료과 선택지는 내과(`D001`), 소아청소년과(`D002`)만 넣었습니다.
- 시군구 이름이 두 단어(예: `수원시 장안구`)일 때 결과가 0건이면 첫 단어(`수원시`)로 한 번 더 조회합니다. 실제 API에서 어느 형식이 맞는지는 Django 이식 때 확인이 필요합니다.
- 카카오 지도 부분은 로컬(Live Server)에서 실제 키로 동작을 확인했습니다. 공공데이터 연동은 **실제 키로 아직 확인하지 않았고**, 가짜 XML 응답으로 필터와 시간 계산만 확인했습니다. 자동 테스트는 없습니다(Django 이식 때 fixture 테스트로 작성).
