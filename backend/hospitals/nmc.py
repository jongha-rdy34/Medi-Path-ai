"""국립중앙의료원 전국 병·의원 찾기 서비스: 병·의원 목록정보 조회 (getHsptlMdcncListInfoInqire).

Spec: 공공데이터포털 참고문서 「NIA-IFT-OpenAPI 활용가이드」 서비스 버전 1.1, 3.1절.
- Q0 시도, Q1 시군구, QD 진료과목(D001..), pageNo, numOfRows. XML only.
- Errors come either as <response><header><resultCode>!=00 or as <OpenAPI_ServiceResponse>
  (e.g. SERVICE_KEY_IS_NOT_REGISTERED_ERROR).
The key is the portal's *Decoding* key; http.get encodes it once (no double encoding).
"""

from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET

from hospitals import http
from hospitals.http import SourceUnavailable

URL = "https://apis.data.go.kr/B552657/HsptlAsembySearchService/getHsptlMdcncListInfoInqire"
PAGE_SIZE = 1000
MAX_PAGES = 20  # safety stop: 20,000 rows is far more than any 시군구 has

log = logging.getLogger(__name__)


def _key() -> str:
    key = os.environ.get("DATA_GO_KR_SERVICE_KEY", "").strip()
    if not key:
        raise SourceUnavailable("nmc", "missing_key")
    return key


def _parse(body: bytes) -> tuple[list[dict], int]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        raise SourceUnavailable("nmc", "not_xml") from None
    if root.tag != "response":
        reason = root.findtext(".//returnAuthMsg") or root.findtext(".//errMsg") or root.tag
        raise SourceUnavailable("nmc", reason.strip())
    code = (root.findtext("header/resultCode") or "").strip()
    if not code or code.strip("0"):  # "00" (or "0000") means success
        raise SourceUnavailable("nmc", f"result_{code or 'missing'}")
    items = [
        {c.tag: (c.text or "").strip() for c in item} for item in root.iterfind("body/items/item")
    ]
    total = int((root.findtext("body/totalCount") or "0").strip() or 0)
    return items, total


def fetch_region(sido: str, sigungu: str | None, department: str | None) -> list[dict]:
    """All clinics in one 시도/시군구 (optionally one NMC department), every page."""
    params = {"serviceKey": _key(), "Q0": sido, "numOfRows": PAGE_SIZE}
    if sigungu:
        params["Q1"] = sigungu
    if department:
        params["QD"] = department

    items: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        page_items, total = _parse(http.get(URL, {**params, "pageNo": page}))
        items.extend(page_items)
        if not page_items or len(items) >= total:
            break
    else:
        log.warning("nmc: stopped after %d pages", MAX_PAGES)
    return items
