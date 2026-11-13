"""Hospital search (T21): Kakao region → NMC clinics (cached per region) → distance + hours filters.

Privacy (SPEC 6, AGENTS 4): the user's coordinates are used for this request only. They are not
stored, logged or put in cache keys. Only 시도/시군구 and the department go into the cache key.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache

from hospitals import hours, kakao, nmc
from hospitals.departments import Department, name_matches

KST = ZoneInfo("Asia/Seoul")
NOTICE = "진료시간은 병원 사정에 따라 바뀔 수 있으니 방문 전에 전화로 확인하세요. 응급 상황이면 119에 연락하세요."


class OutOfServiceArea(Exception):
    """Coordinates do not resolve to a Korean 시도 (sea, abroad)."""


@dataclass(frozen=True)
class Query:
    lat: float
    lng: float
    department: Department
    radius: int = 3000
    open_now: bool = False
    night: bool = False
    weekend: bool = False
    limit: int = 30


def now() -> datetime:
    return datetime.now(KST)


def cache_seconds() -> int:
    return int(getattr(settings, "HOSPITALS_CACHE_SECONDS", 6 * 60 * 60))


def cache_key(sido: str, sigungu: str | None, nmc_department: str | None) -> str:
    raw = f"{sido}|{sigungu or ''}|{nmc_department or ''}"
    return "hospitals:nmc:v1:" + hashlib.sha1(raw.encode()).hexdigest()


def _clinics(sido: str, sigungu: str | None, nmc_department: str | None) -> list[dict]:
    key = cache_key(sido, sigungu, nmc_department)
    items = cache.get(key)
    if items is None:
        items = nmc.fetch_region(sido, sigungu, nmc_department)
        cache.set(key, items, cache_seconds())
    return items


def nmc_sigungu(sigungu: str | None) -> str | None:
    """NMC Q1 for a Kakao 시군구. Two-word names ("수원시 장안구") become the city ("수원시").

    Live check 2026-11-12 (hospital_live_check): NMC returned 0 for "수원시 장안구",
    "성남시 분당구", "전주시 완산구" and 506 / 463 / 312 for "수원시" / "성남시" / "전주시".
    New province names (강원특별자치도, 전북특별자치도) work as Q0; the old names return 0.
    """
    if sigungu and " " in sigungu:
        return sigungu.split()[0]
    return sigungu


def _clinics_for_region(region: dict, nmc_department: str | None) -> list[dict]:
    return _clinics(region["sido"], nmc_sigungu(region["sigungu"]), nmc_department)


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """Haversine distance in metres."""
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)))


def _josa_eun_neun(word: str) -> str:
    last = word[-1] if word else ""
    has_final = "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 != 0
    return "은" if has_final else "는"


def _hospital(item: dict, q: Query, when: datetime, filtered: bool) -> dict | None:
    try:
        lat, lng = float(item["wgs84Lat"]), float(item["wgs84Lon"])
    except (KeyError, ValueError):
        return None  # no coordinates: cannot place it on the map
    return {
        "hospital_id": item.get("hpid", ""),
        "name": item.get("dutyName", ""),
        "type": item.get("dutyDivNam", ""),
        "address": item.get("dutyAddr", ""),
        "phone": item.get("dutyTel1") or None,
        "location": {"lat": lat, "lng": lng},
        "distance_m": distance_m(q.lat, q.lng, lat, lng),
        "department": q.department.code if filtered else None,
        "opening_hours": hours.opening_hours(item),
        "is_open_now": hours.is_open_at(item, when),
        "has_night_hours": hours.has_night_hours(item),
        "has_weekend_hours": hours.has_weekend_hours(item),
        "has_emergency_room": None,  # T60
    }


def search(q: Query) -> dict:
    region = kakao.region_of(q.lat, q.lng)
    if region is None:
        raise OutOfServiceArea
    dept = q.department
    filtered = dept.nmc_code is not None
    when = now()

    found = []
    for item in _clinics_for_region(region, dept.nmc_code):
        h = _hospital(item, q, when, filtered)
        if h is None or h["distance_m"] > q.radius:
            continue
        if filtered and not name_matches(dept.code, h["name"], h["type"]):
            continue  # lists the department but is another specialty (decision 2026-11-12)
        if q.open_now and h["is_open_now"] is not True:
            continue
        if q.night and not h["has_night_hours"]:
            continue
        if q.weekend and not h["has_weekend_hours"]:
            continue
        found.append(h)
    found.sort(key=lambda h: (h["distance_m"], h["name"]))

    message = None
    if not filtered:
        message = (
            f"{dept.name}{_josa_eun_neun(dept.name)} 병원 정보에서 진료과로 구분되지 않아 "
            "근처 병원 전체를 보여 드려요."
        )
    return {
        "total": len(found),
        "items": found[: q.limit],
        "region": region,
        "department": {
            "code": dept.code,
            "name": dept.name,
            "filter_applied": filtered,
            "message": message,
        },
        "evaluated_at": when.isoformat(timespec="seconds"),
        "notice": NOTICE,
    }
