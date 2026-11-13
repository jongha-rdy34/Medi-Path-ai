"""Tests on REAL responses recorded with hospital_live_check (2026-11-12, trimmed).

fixtures/recorded/: NMC 내과(D001) lists for 서울 서초구 (first 40) and 경기 수원시 (12, including two
clinics with 18:30~18:30 weekday hours), and Kakao regions for 강남역, 수원 장안구청, 춘천시청.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from hospitals import hours, kakao, nmc, service
from hospitals.tests.conftest import fixture
from tests.contract import validate

WED_2PM = datetime(2026, 11, 11, 14, 0, tzinfo=ZoneInfo("Asia/Seoul"))
GANGNAM_STATION = {"lat": "37.4979", "lng": "127.0276"}


@pytest.fixture
def real(fake_http, monkeypatch):
    monkeypatch.setattr(service, "now", lambda: WED_2PM)
    fake_http.kakao = fixture("recorded/kakao_gangnam_station.json")
    fake_http.nmc_pages = [fixture("recorded/nmc_seoul_seocho_D001.xml")]
    return fake_http


def test_real_nmc_items_parse(real):
    items = nmc.fetch_region("서울특별시", "서초구", "D001")

    assert len(items) == 40
    assert all(i["hpid"] and i["dutyName"] and i["wgs84Lat"] and i["wgs84Lon"] for i in items)


def test_real_search_matches_contract(client, real):
    res = client.get("/api/hospitals", {**GANGNAM_STATION, "department": "01", "radius": 10000})
    body = res.json()

    assert res.status_code == 200
    validate(body, "HospitalSearchResponse")
    assert body["total"] > 0
    distances = [h["distance_m"] for h in body["items"]]
    assert distances == sorted(distances)
    # Wed 14:00: most 내과 clinics are open; the flag must never be null when hours exist.
    assert any(h["is_open_now"] for h in body["items"])
    assert all(h["is_open_now"] is not None for h in body["items"] if h["opening_hours"])


def test_gangnam_station_point_resolves_to_seocho(real):
    """Known limitation, seen live: 강남역 sits on the 강남구/서초구 border; only 서초구 is searched."""
    assert kakao.region_of(37.4979, 127.0276) == {"sido": "서울특별시", "sigungu": "서초구"}


def test_real_two_word_sigungu_and_new_province_name(fake_http):
    fake_http.kakao = fixture("recorded/kakao_suwon_jangan_gu_office.json")
    suwon = kakao.region_of(37.3039, 127.0101)
    fake_http.kakao = fixture("recorded/kakao_chuncheon_city_hall.json")
    chuncheon = kakao.region_of(37.8813, 127.7298)

    assert suwon == {"sido": "경기도", "sigungu": "수원시 장안구"}
    assert service.nmc_sigungu(suwon["sigungu"]) == "수원시"
    assert chuncheon["sido"] == "강원특별자치도"  # NMC accepts the new name as Q0


def test_real_same_open_and_close_days_are_ignored(fake_http):
    fake_http.nmc_pages = [fixture("recorded/nmc_gyeonggi_suwon_D001.xml")]
    items = {i["dutyName"]: i for i in nmc.fetch_region("경기도", "수원시", "D001")}

    best = items["서울베스트내과의원"]  # Mon~Fri 18:30~18:30, Sat 08:30~14:00
    assert [d["day"] for d in hours.opening_hours(best)] == ["sat"]
    assert hours.is_open_at(best, WED_2PM) is False
    assert hours.has_weekend_hours(best) is True
