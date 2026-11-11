#!/usr/bin/env bash
# 공공데이터포털 API 키 확인 스크립트 (T03). 키를 받은 뒤 저장소 루트에서 실행합니다.
#
#   bash infra/scripts/check-public-apis.sh            # 실제 호출(각 API 1회)
#   bash infra/scripts/check-public-apis.sh --dry-run  # 보낼 요청만 출력(키는 가림)
#
# 키는 .env의 DATA_GO_KR_SERVICE_KEY에서 읽습니다. 포털의 "일반 인증키(Decoding)"를 넣으세요.
# 요청 주소는 미검증 기본값입니다(docs/api-keys.md). 활용신청 페이지의 "요청주소"와 다르면 .env에서 바꾸세요.
#
# 종료 코드: 0 모두 정상 / 1 하나 이상 실패 / 2 키 없음 또는 잘못된 사용법
set -euo pipefail

cd "$(dirname "$0")/../.."
DRY_RUN=false
case "${1:-}" in
  "") ;;
  --dry-run) DRY_RUN=true ;;
  *) echo "사용법: $0 [--dry-run]" >&2; exit 2 ;;
esac

# .env에서 필요한 값만 읽습니다(파일 전체를 실행하지 않음).
read_env() {
  local name="$1"
  if [[ -z "${!name:-}" && -f .env ]]; then
    local line
    line="$(grep -E "^${name}=" .env | tail -n 1 || true)"
    if [[ -n "$line" ]]; then
      printf -v "$name" '%s' "${line#*=}"
    fi
  fi
}
read_env DATA_GO_KR_SERVICE_KEY
read_env HIRA_HOSP_LIST_URL
read_env NMC_ER_BEDS_URL
read_env NMC_CLINIC_LIST_URL

if [[ -z "${DATA_GO_KR_SERVICE_KEY:-}" ]]; then
  echo "DATA_GO_KR_SERVICE_KEY가 없습니다. .env에 공공데이터포털 일반 인증키(Decoding)를 넣으세요. 절차: docs/api-keys.md" >&2
  exit 2
fi

HIRA_HOSP_LIST_URL="${HIRA_HOSP_LIST_URL:-https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList}"
NMC_ER_BEDS_URL="${NMC_ER_BEDS_URL:-https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire}"
NMC_CLINIC_LIST_URL="${NMC_CLINIC_LIST_URL:-https://apis.data.go.kr/B552657/HsptlAsembySearchService/getHsptlMdcncListInfoInqire}"

failures=0

# check <이름> <URL> [추가 파라미터...]
check() {
  local name="$1" url="$2"
  shift 2
  local params=(--data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" --data-urlencode "pageNo=1" --data-urlencode "numOfRows=1")
  local p
  for p in "$@"; do params+=(--data-urlencode "$p"); done

  echo "== ${name}"
  echo "   GET ${url}?serviceKey=****&pageNo=1&numOfRows=1$(printf '&%s' "$@")"
  if $DRY_RUN; then
    return 0
  fi

  local body err status
  body="$(mktemp)"
  err="$(mktemp)"
  if ! status="$(curl -sS -G -m 20 -o "$body" -w '%{http_code}' "${params[@]}" "$url" 2>"$err")"; then
    echo "   요청 실패: $(head -c 200 "$err")"
    failures=$((failures + 1))
    rm -f "$body" "$err"
    return 0
  fi
  # 정상 응답은 resultCode(XML/JSON), 인증 오류는 returnReasonCode/returnAuthMsg로 옵니다.
  local code msg
  code="$(sed -nE 's/.*<resultCode>([^<]*)<\/resultCode>.*/\1/p; s/.*"resultCode" *: *"([^"]*)".*/\1/p; s/.*<returnReasonCode>([^<]*)<\/returnReasonCode>.*/\1/p' "$body" | head -n 1)"
  msg="$(sed -nE 's/.*<resultMsg>([^<]*)<\/resultMsg>.*/\1/p; s/.*"resultMsg" *: *"([^"]*)".*/\1/p; s/.*<returnAuthMsg>([^<]*)<\/returnAuthMsg>.*/\1/p' "$body" | head -n 1)"
  echo "   HTTP ${status}  resultCode=${code:-없음}  ${msg}"
  if [[ "$status" == "200" && ( "$code" == "00" || "$code" == "0" ) ]]; then
    echo "   정상"
  else
    echo "   실패: 응답 앞부분 ↓"
    head -c 300 "$body" | sed 's/^/   | /'
    echo
    failures=$((failures + 1))
  fi
  rm -f "$body" "$err"
}

check "국립중앙의료원 전국 병·의원 찾기 (T21 MVP)" "$NMC_CLINIC_LIST_URL" "Q0=서울특별시" "Q1=강남구"
check "건강보험심사평가원 병원정보서비스 (병원 목록)" "$HIRA_HOSP_LIST_URL" "_type=json"
check "국립중앙의료원 응급실 실시간 가용병상" "$NMC_ER_BEDS_URL" "STAGE1=서울특별시" "STAGE2=강남구"

if $DRY_RUN; then
  echo "dry-run: 실제로 호출하지 않았습니다"
  exit 0
fi
if (( failures > 0 )); then
  echo "실패 ${failures}건. 오류 코드 설명: docs/api-keys.md"
  exit 1
fi
echo "모두 정상"
