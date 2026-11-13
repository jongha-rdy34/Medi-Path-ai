# features/hospitals — `<HospitalFinder>` (T21 PR 4, @ley-21)

결과 화면에 한 줄로 끼우는 병원 찾기 컴포넌트입니다. 프로토타입(`prototypes/kakao-hospital-search/public/index.html`)의 지도·목록을 Vue로 옮겼습니다.

```vue
<HospitalFinder :department="권장 진료과 코드(심평원, 예 '01')" />
```

- 받는 값은 `department` 하나뿐입니다. 진료과 드롭다운의 초기값이고, 사용자가 바꿀 수 있습니다.
- 루트 요소는 `data-test="hospital-finder"`, `data-department`를 유지합니다(결과 화면 테스트·e2e가 사용).
- 위급 결과에서는 결과 화면이 이 컴포넌트를 넣지 않습니다(119·응급실 안내로 대체).

| 파일 | 역할 |
|---|---|
| `HospitalFinder.vue` | 위치 권한 → `GET /api/hospitals` → 목록 + 지도. 진료과·반경·지금 진료 중·야간·주말 |
| `api.ts`, `types.ts` | 계약(`contracts/openapi.yaml` `searchHospitals`) 호출과 타입 |
| `kakaoMap.ts` | 카카오 지도 SDK 래퍼(지도, 내 위치, 반경 원, 마커, 말풍선, 지도 클릭) |
| `departments.ts` | 진료과 목록(`data/mappings/departments.csv` 복사본, 테스트가 일치 확인) |
| `format.ts` | 거리, 요일별 진료시간, "진료 중" 배지 |

## 동작
- 위치를 허용하면 그 위치로 검색합니다. 거부·실패하면 이유를 보여 주고, **지도를 누르면 그 지점 기준으로** 검색합니다. 위치를 모르면 검색하지 않습니다(엉뚱한 기본 위치 결과를 보여 주지 않음).
- 위치는 이번 검색에만 쓰고 저장하지 않습니다(localStorage 등 없음).
- 지도를 못 불러와도(키 없음, SDK 차단) 목록은 동작합니다.
- 서버 안내(`notice`), 진료과 조건을 못 건 경우의 안내(`department.message`), "12:00 기준"을 목록 위에 보여 줍니다.

## 키
`VITE_KAKAO_MAP_JS_KEY`(카카오 **JavaScript** 키). 브라우저에 보이는 키라 카카오 콘솔의 JavaScript SDK 도메인에 접속 주소를 포트까지 등록해 보호합니다(`http://localhost:5173`). docker compose는 루트 `.env` 값을 넘깁니다.

## 테스트
```bash
cd frontend && npm run test    # 지도 SDK와 API는 가짜로 대체
```
