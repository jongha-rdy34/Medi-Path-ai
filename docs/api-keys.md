# 공공 API 키 발급 절차 (T03)

> 범위(2026-11-11 변경): **Kakao 키는 팀원이 이미 가지고 있어** 여기서 다루지 않습니다. MVP 병원 검색은 Kakao 로컬 API(T21, 팀원 담당)입니다.
> 이 문서는 4~5주차(T60)에 쓸 **공공데이터포털** API 두 개를 미리 신청하는 절차입니다. 승인에 시간이 걸릴 수 있어 미리 받아 둡니다.

**검증 상태**: 이 문서를 작성한 세션에서는 data.go.kr에 접근할 수 없어서, 아래 서비스 이름과 요청 주소는 **공식 페이지에서 확인하지 못했습니다(미검증)**.
신청할 때 각 서비스 상세 페이지의 "요청주소"와 "요청변수"를 확인하고, 다르면 `.env`의 `HIRA_HOSP_LIST_URL`, `NMC_ER_BEDS_URL`로 바꾸세요. 확인한 뒤 이 문단을 지워 주세요.

## 1. 신청할 API

| 용도 | 포털 검색어 | 기본 요청 주소(미검증) | 쓰는 곳 |
|---|---|---|---|
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

- 두 API를 각각 1회(1건) 호출하고, `resultCode=00`이면 "정상"입니다. 키는 출력에서 가려집니다.
- 종료 코드: 0 모두 정상 / 1 하나 이상 실패 / 2 키 없음

## 4. 자주 보는 오류

| 출력 | 뜻 | 할 일 |
|---|---|---|
| `SERVICE_KEY_IS_NOT_REGISTERED_ERROR` (30) | 키가 아직 등록되지 않음 | 승인 직후에는 반영까지 시간이 걸리는 경우가 많습니다. 1~2시간 뒤 다시 실행. Encoding 키를 넣었다면 Decoding 키로 교체 |
| `LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR` (22) | 일일 트래픽 초과 | 다음 날 재시도. 폴링 간격 조정 |
| `NO_OPENAPI_SERVICE_ERROR` (12) | 서비스가 없거나 폐기됨 | 상세 페이지의 요청주소로 `.env`의 URL 변경 |
| 코드 10 / `INVALID_REQUEST_PARAMETER_ERROR` | 요청 변수가 맞지 않음 | 상세 페이지의 요청변수 확인 후 스크립트 파라미터 수정 |
| `요청 실패: curl ...` | 네트워크 문제 | 인터넷 연결, 회사·학교 방화벽 확인 |

## 5. 키 관리 규칙
- 키는 `.env`에만 둡니다. 저장소는 public이라 커밋하면 바로 노출됩니다(push protection이 막아도 키를 재발급해야 합니다).
- 키를 채팅, 이슈, PR 본문에 붙여 넣지 않습니다.
- 배포 서버에서는 서버의 `.env`에 따로 넣습니다(T31).
