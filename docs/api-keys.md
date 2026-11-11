# 공공 API·Kakao 키 발급 절차 (T03)

> 2026-11-11 확정: MVP 병원 검색(T21, @ley-21)은 **국립중앙의료원 전국 병·의원 찾기 서비스**를 쓰고, Kakao는 지도와 좌표 → 시도·시군구 변환에만 씁니다.
> 공공데이터포털 API 3개와 Kakao 앱 설정을 다룹니다. 키 이름: `DATA_GO_KR_SERVICE_KEY`, `KAKAO_REST_API_KEY`, `VITE_KAKAO_MAP_JS_KEY`.

**검증 상태**: 이 문서를 작성한 세션에서는 data.go.kr에 접근할 수 없어서, 아래 서비스 이름과 요청 주소는 **공식 페이지에서 확인하지 못했습니다(미검증)**.
신청할 때 각 서비스 상세 페이지의 "요청주소"와 "요청변수"를 확인하고, 다르면 `.env`의 `NMC_CLINIC_LIST_URL`, `HIRA_HOSP_LIST_URL`, `NMC_ER_BEDS_URL`로 바꾸세요. (병·의원 찾기의 오퍼레이션 이름은 팀원 프로토타입에서 쓰는 이름입니다.) 확인한 뒤 이 문단을 지워 주세요.

## 1. 신청할 API

| 용도 | 포털 검색어 | 기본 요청 주소(미검증) | 쓰는 곳 |
|---|---|---|---|
| **병원 검색(MVP)**: 시도·시군구·진료과, 좌표, 요일별 진료시간 | `국립중앙의료원_전국 병·의원 찾기 서비스` | `https://apis.data.go.kr/B552657/HsptlAsembySearchService/getHsptlMdcncListInfoInqire` | **T21 (지금 필요)** |
| 병원 목록(진료과목, 좌표) | `건강보험심사평가원_병원정보서비스` | `https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList` | T60 심평원 적재·ES geo 검색, T62 일일 갱신 |
| 응급실 실시간 가용 병상 | `국립중앙의료원_전국 응급의료기관 정보 조회 서비스` | `https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire` | T60 Kafka 수집 |

## 2. 신청 순서 (공공데이터포털, https://www.data.go.kr)

1. 회원가입 후 로그인합니다.
2. 위 검색어로 검색해 **오픈 API** 탭의 서비스를 엽니다.
3. **활용신청**을 누르고 활용 목적에 "포트폴리오 웹 서비스(MediPath) 개발, 비상업"이라고 적습니다. 개발계정으로 신청합니다.
4. **마이페이지 → 데이터활용 → Open API → 활용신청 현황**에서 승인 상태를 봅니다. 자동 승인되는 서비스가 많지만, 심의가 필요한 서비스도 있습니다.
5. 같은 화면에서 **일반 인증키**를 확인합니다. Encoding/Decoding 두 가지가 보이면 **Decoding** 값을 씁니다(스크립트가 URL 인코딩을 직접 합니다).
6. 상세 페이지에서 **일일 트래픽 한도**를 확인해 여기에 적어 둡니다. T60은 1~5분 간격으로 폴링하므로 한도를 넘지 않게 간격을 정해야 합니다.

## 3. 키 넣고 확인하기

```bash
cp .env.example .env
```

`.env`의 `DATA_GO_KR_SERVICE_KEY=` 뒤에 Decoding 키를 붙여 넣은 뒤:

```bash
bash infra/scripts/check-public-apis.sh --dry-run
```

```bash
bash infra/scripts/check-public-apis.sh
```

- 세 API를 각각 1회(1건) 호출하고, `resultCode=00`이면 "정상"입니다. 키는 출력에서 가려집니다.
- 종료 코드: 0 모두 정상 / 1 하나 이상 실패 / 2 키 없음

## 4. 자주 보는 오류

| 출력 | 뜻 | 할 일 |
|---|---|---|
| `SERVICE_KEY_IS_NOT_REGISTERED_ERROR` (30) | 키가 아직 등록되지 않음, 또는 키가 이중 인코딩됨 | 승인 직후에는 반영까지 시간이 걸리는 경우가 많습니다. 1~2시간 뒤 다시 실행. Encoding 키를 넣었다면 Decoding 키로 교체 |
| `LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR` (22) | 일일 트래픽 초과 | 다음 날 재시도. 폴링 간격 조정 |
| `NO_OPENAPI_SERVICE_ERROR` (12) | 서비스가 없거나 폐기됨 | 상세 페이지의 요청주소로 `.env`의 URL 변경 |
| 코드 10 / `INVALID_REQUEST_PARAMETER_ERROR` | 요청 변수가 맞지 않음 | 상세 페이지의 요청변수 확인 후 스크립트 파라미터 수정 |
| `요청 실패: curl ...` | 네트워크 문제 | 인터넷 연결, 회사·학교 방화벽 확인 |

## 5. 이중 인코딩 주의 (공공데이터포털 키)

포털은 같은 키를 Encoding(이미 `%2B` 등으로 인코딩됨)과 Decoding(원래 문자 `+`, `/`, `=`) 두 형태로 보여 줍니다.
- `.env`에는 **Decoding 키**를 넣고, 코드에서는 HTTP 라이브러리가 쿼리를 인코딩하게 둡니다(`requests`의 `params=`, `curl --data-urlencode`, `URLSearchParams`).
- Encoding 키를 넣거나, Decoding 키를 직접 인코딩한 뒤 라이브러리가 한 번 더 인코딩하면 `%2B`가 `%252B`가 되어 **30번 오류**가 납니다.
- 서버 코드(T21 PR 3)에서 URL 문자열을 직접 이어 붙이지 마세요.

## 6. Kakao 앱 설정 (T21, 키는 팀원이 이미 발급)

1. **앱 하나를 공동 관리**합니다. Kakao Developers → 내 애플리케이션 → 해당 앱 → **팀 관리**에서 다른 팀원을 멤버로 추가합니다. 각자 앱을 따로 만들지 않습니다(키와 도메인 설정이 갈라짐).
2. **카카오맵 사용 설정**: 앱 설정의 **카카오맵** 메뉴에서 [사용 설정]을 **ON**으로 켭니다. 꺼져 있으면 지도 SDK가 로드되지 않습니다.
3. **Web 플랫폼 도메인**: 플랫폼 → Web → 사이트 도메인에 `http://localhost:5173`을 **포트까지 정확히** 등록합니다(`http://localhost`만으로는 안 됨). 배포(T31) 때 `https://<배포 도메인>`을 추가합니다.
4. **키 사용처**
   - `KAKAO_REST_API_KEY`: 서버 전용. 좌표 → 시도·시군구 변환(`coord2regioncode`)에만 씁니다. 프론트로 보내지 않습니다.
   - `VITE_KAKAO_MAP_JS_KEY`: 브라우저에 노출되는 키입니다. 3번의 도메인 등록이 보호 수단입니다.
5. **로컬 API 결과 저장 금지**: Kakao 로컬 API 응답(지역 변환 결과 포함)은 DB·파일·캐시에 저장하지 않습니다(Kakao 정책, SPEC 결정 표). 좌표는 캐시 키에도 넣지 않습니다.
6. **휴대폰 위치 권한**: 브라우저의 위치 API는 보안 컨텍스트(https 또는 localhost)에서만 동작합니다. 휴대폰으로 `http://<PC IP>:5173`에 접속하면 위치를 받지 못하므로, 위치 실패 시 지도 클릭으로 지정하는 대체 흐름을 씁니다. 실제 휴대폰 확인은 https 배포(T31) 후에 합니다.

이 절의 Kakao 콘솔 메뉴 이름은 이 세션에서 공식 문서(developers.kakao.com)에 접근할 수 없어 확인하지 못했습니다. 화면과 다르면 고쳐 주세요.

## 7. 키 관리 규칙
- 키는 `.env`에만 둡니다. 저장소는 public이라 커밋하면 바로 노출됩니다(push protection이 막아도 키를 재발급해야 합니다).
- 키를 채팅, 이슈, PR 본문에 붙여 넣지 않습니다.
- 배포 서버에서는 서버의 `.env`에 따로 넣습니다(T31).
