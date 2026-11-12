"""GET /api/hospitals end to end with fake HTTP (contract: contracts/openapi.yaml, T21 PR 2)."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from hospitals import service
from hospitals.http import SourceUnavailable
from hospitals.tests.conftest import fixture
from tests.contract import validate

URL = "/api/hospitals"
GANGNAM = {"lat": "37.4979", "lng": "127.0276"}
WED_8PM = datetime(2026, 11, 11, 20, 0, tzinfo=ZoneInfo("Asia/Seoul"))


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(service, "now", lambda: WED_8PM)


def get(client, **params):
    return client.get(URL, {**GANGNAM, "department": "01", **params})


def names(res):
    return [h["name"] for h in res.json()["items"]]


def test_matches_contract_and_sorts_by_distance(client, fake_http):
    res = get(client)

    assert res.status_code == 200
    body = res.json()
    validate(body, "HospitalSearchResponse")
    # The 4th hospital is ~3.6 km away, outside the default 3 km radius.
    assert names(res) == ["가까운내과의원", "주말병원", "심야내과의원"]
    distances = [h["distance_m"] for h in body["items"]]
    assert distances == sorted(distances)
    assert body["total"] == 3
    assert body["region"] == {"sido": "서울특별시", "sigungu": "강남구"}
    assert body["department"] == {
        "code": "01",
        "name": "내과",
        "filter_applied": True,
        "message": None,
    }
    assert body["evaluated_at"] == "2026-11-11T20:00:00+09:00"
    assert "119" in body["notice"]
    assert fake_http.nmc_calls()[0]["params"]["QD"] == "D001"


def test_hospital_fields(client, fake_http):
    first = get(client).json()["items"][0]

    assert first["hospital_id"] == "T0000001"
    assert first["type"] == "의원"
    assert first["phone"] == "02-000-0001"
    assert first["department"] == "01"
    assert first["has_emergency_room"] is None
    assert first["opening_hours"][2] == {
        "day": "wed",
        "open": "09:00",
        "close": "21:00",
        "crosses_midnight": False,
    }


def test_missing_phone_is_null(client, fake_http):
    late = next(h for h in get(client).json()["items"] if h["name"] == "심야내과의원")
    assert late["phone"] is None


def test_wider_radius_includes_far_hospital_without_hours(client, fake_http):
    res = get(client, radius=5000)
    far = res.json()["items"][-1]

    assert far["name"] == "시간정보없는의원"
    assert far["opening_hours"] == []
    assert far["is_open_now"] is None


@pytest.mark.parametrize(
    ("flag", "expected"),
    [
        ("open_now", ["가까운내과의원", "심야내과의원"]),  # Wed 20:00
        ("night", ["가까운내과의원", "심야내과의원"]),  # Wed until 21:00 / past midnight
        ("weekend", ["가까운내과의원", "주말병원"]),  # Sat / Sat+Sun
    ],
)
def test_filters(client, fake_http, flag, expected):
    res = get(client, **{flag: "true"})

    assert res.status_code == 200
    assert names(res) == expected
    assert res.json()["total"] == len(expected)


def test_filters_combine(client, fake_http):
    assert names(get(client, open_now="true", weekend="true")) == ["가까운내과의원"]


def test_open_now_after_midnight_uses_previous_day(client, fake_http, monkeypatch):
    monkeypatch.setattr(
        service, "now", lambda: datetime(2026, 11, 12, 1, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    )
    assert names(get(client, open_now="true")) == ["심야내과의원"]


def test_limit_cuts_items_not_total(client, fake_http):
    body = get(client, limit=1).json()
    assert len(body["items"]) == 1
    assert body["total"] == 3


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"department": "77"}, "department"),  # not in departments.csv
        ({"department": "내과"}, "department"),
        ({"lat": "91"}, "lat"),
        ({"radius": "20000"}, "radius"),
        ({"limit": "0"}, "limit"),
        ({"open_now": "maybe"}, "open_now"),
    ],
)
def test_validation_errors(client, fake_http, params, field):
    res = get(client, **params)

    assert res.status_code == 422
    validate(res.json(), "Error")
    assert res.json()["code"] == "validation_error"
    assert field in [d["field"] for d in res.json()["details"]]
    assert fake_http.calls == []


def test_missing_department_is_rejected(client, fake_http):
    res = client.get(URL, GANGNAM)
    assert res.status_code == 422
    assert "department" in [d["field"] for d in res.json()["details"]]


def test_department_without_nmc_code_searches_all(client, fake_http):
    res = get(client, department="00")  # 일반의
    body = res.json()

    assert res.status_code == 200
    validate(body, "HospitalSearchResponse")
    assert body["department"]["filter_applied"] is False
    assert body["department"]["name"] == "일반의"
    assert "일반의는" in body["department"]["message"]
    assert all(h["department"] is None for h in body["items"])
    assert "QD" not in fake_http.nmc_calls()[0]["params"]


def test_nmc_code_column_in_departments_csv_is_used(client, fake_http, settings, tmp_path):
    (tmp_path / "departments.csv").write_text(
        "code,name_ko,source,nmc_code\n01,내과,x,D001\n11,소아청소년과,x,D002\n00,일반의,x,\n",
        encoding="utf-8",
    )
    settings.MAPPINGS_DIR = tmp_path

    res = get(client, department="11")

    assert res.json()["department"]["filter_applied"] is True
    assert fake_http.nmc_calls()[0]["params"]["QD"] == "D002"


def test_sea_is_out_of_service_area(client, fake_http):
    fake_http.kakao = fixture("kakao_sea.json")
    res = get(client)

    assert res.status_code == 422
    validate(res.json(), "Error")
    assert res.json()["code"] == "out_of_service_area"
    assert fake_http.nmc_calls() == []


def test_upstream_failure_is_503(client, fake_http):
    fake_http.error = SourceUnavailable("nmc", "timeout")
    res = get(client)

    assert res.status_code == 503
    validate(res.json(), "Error")
    assert res.json()["code"] == "hospital_source_unavailable"


def test_nmc_cached_per_region_not_per_coordinate(client, fake_http):
    get(client)
    get(client, lat="37.4990", lng="127.0300")  # other point, same 구

    assert len(fake_http.nmc_calls()) == 2  # 2 pages fetched once
    kakao_calls = [c for c in fake_http.calls if "kakao" in c["url"]]
    assert len(kakao_calls) == 2  # Kakao results are never cached (policy)
    assert "37.49" not in service.cache_key("서울특별시", "강남구", "D001")


def test_two_word_sigungu_falls_back_to_city(client, fake_http):
    fake_http.kakao = fixture("kakao_bundang.json")
    fake_http.nmc_by_q1 = {"성남시 분당구": [fixture("nmc_empty.xml")]}

    res = get(client)

    assert res.status_code == 200
    assert [c["params"]["Q1"] for c in fake_http.nmc_calls()] == [
        "성남시 분당구",
        "성남시",
        "성남시",
    ]
    assert res.json()["region"] == {"sido": "경기도", "sigungu": "성남시 분당구"}


def test_no_coordinates_or_keys_in_logs(client, fake_http, caplog):
    caplog.set_level(logging.DEBUG)
    get(client)
    fake_http.error = SourceUnavailable("nmc", "SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
    get(client, department="00")

    text = caplog.text
    assert "37.4979" not in text and "127.0276" not in text
    assert "test-nmc-key" not in text and "test-kakao-key" not in text
