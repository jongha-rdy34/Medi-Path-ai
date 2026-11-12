"""Kakao Local: 좌표로 행정구역정보 변환 (coord2regioncode).

Docs: https://developers.kakao.com/docs/latest/ko/local/dev-guide (좌표로 행정구역정보 변환하기)
- GET https://dapi.kakao.com/v2/local/geo/coord2regioncode.json?x={lng}&y={lat}
- Header: Authorization: KakaoAK {REST_API_KEY}
- documents[]: region_type B(법정동)/H(행정동), region_1depth_name(시도), region_2depth_name(시군구,
  may be two words like "성남시 분당구"). Sea areas return no documents.
Policy: results are used live and never stored or cached (Kakao terms).
"""

from __future__ import annotations

import json
import os

from hospitals import http
from hospitals.http import SourceUnavailable

URL = "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json"


def _key() -> str:
    key = os.environ.get("KAKAO_REST_API_KEY", "").strip()
    if not key:
        raise SourceUnavailable("kakao", "missing_key")
    return key


def region_of(lat: float, lng: float) -> dict | None:
    """{"sido", "sigungu"} for the point, or None when it is not in a Korean region (sea, abroad)."""
    body = http.get(URL, {"x": lng, "y": lat}, headers={"Authorization": f"KakaoAK {_key()}"})
    try:
        docs = json.loads(body).get("documents") or []
    except (ValueError, AttributeError):
        raise SourceUnavailable("kakao", "not_json") from None

    doc = next((d for d in docs if d.get("region_type") == "B"), docs[0] if docs else None)
    if not doc or not (doc.get("region_1depth_name") or "").strip():
        return None
    sido = doc["region_1depth_name"].strip()
    sigungu = (doc.get("region_2depth_name") or "").strip() or None
    if sido.startswith("세종"):
        sigungu = None  # 세종특별자치시 has no 시군구
    return {"sido": sido, "sigungu": sigungu}
