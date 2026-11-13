"""GET /api/hospitals end to end with fake HTTP (contract: contracts/openapi.yaml, T21 PR 2)."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from hospitals import service
from hospitals.http import SourceUnavailable
from hospitals.tests.conftest import fixture, kakao_region, nmc_xml
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
    # 튼튼정형외과의원 is filtered out by name; 시간정보없는내과의원 is ~3.6 km away (radius 3 km).
    assert names(res) == ["가까운내과의원", "주말내과병원", "심야내과의원", "예시대학교병원"]
    distances = [h["distance_m"] for h in body["items"]]
    assert distances == sorted(distances)
    assert body["total"] == 4
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

    assert far["name"] == "시간정보없는내과의원"
    assert far["opening_hours"] == []
    assert far["is_open_now"] is None


@pytest.mark.parametrize(
    ("flag", "expected"),
    [
        ("open_now", ["가까운내과의원", "심야내과의원"]),  # Wed 20:00 (대학병원 closes 17:00)
        ("night", ["가까운내과의원", "심야내과의원"]),  # Wed until 21:00 / past midnight
        ("weekend", ["가까운내과의원", "주말내과병원"]),  # Sat / Sat+Sun
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
    assert body["total"] == 4


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


def test_clinics_need_the_department_in_their_name(client, fake_http):
    """Decision 2026-11-12 (@ley-21): NMC QD also returns clinics that merely list 내과
    (e.g. an orthopedic clinic). Clinics(의원) and hospitals(병원) must carry the department
    in their name; 종합병원 is kept because it really runs many departments."""
    found = names(get(client))

    assert "튼튼정형외과의원" not in found
    assert "예시대학교병원" in found  # 종합병원


def test_name_rule_not_applied_without_department_filter(client, fake_http):
    found = names(get(client, department="00"))  # 일반의: no NMC code, no filter
    assert "튼튼정형외과의원" in found


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
    assert len(fake_http.kakao_calls()) == 2 * 9  # center + 8 ring points, never cached (policy)
    assert "37.49" not in service.cache_key("서울특별시", "강남구", "D001")


def test_two_word_sigungu_queries_the_city(client, fake_http):
    """Live check 2026-11-12: NMC Q1 returns 0 for "성남시 분당구"/"수원시 장안구", >0 for the city."""
    fake_http.kakao = fixture("kakao_bundang.json")

    res = get(client)

    assert res.status_code == 200
    assert {c["params"]["Q1"] for c in fake_http.nmc_calls()} == {"성남시"}
    assert res.json()["region"] == {"sido": "경기도", "sigungu": "성남시 분당구"}


def test_no_coordinates_or_keys_in_logs(client, fake_http, caplog):
    caplog.set_level(logging.DEBUG)
    get(client)
    fake_http.error = SourceUnavailable("nmc", "SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
    get(client, department="00")

    text = caplog.text
    assert "37.4979" not in text and "127.0276" not in text
    assert "test-nmc-key" not in text and "test-kakao-key" not in text


# --- radius across districts (decision 2026-11-12, @ley-21; #15) ---------------------------
def test_sample_points_are_center_and_ring_at_radius():
    points = service.sample_points(37.4979, 127.0276, 3000)

    assert points[0] == (37.4979, 127.0276)
    assert len(points) == 9
    for lat, lng in points[1:]:
        assert abs(service.distance_m(37.4979, 127.0276, lat, lng) - 3000) < 30


def test_radius_crossing_a_border_searches_both_districts(client, fake_http):
    """강남역 case seen live: the point is in 서초구 but the 3 km circle reaches 강남구."""
    fake_http.kakao_for = lambda lat, lng: (
        kakao_region("서울특별시", "서초구")
        if lng < 127.03
        else kakao_region("서울특별시", "강남구")
    )
    fake_http.nmc_by_q1 = {
        "서초구": [nmc_xml(("S1", "서초내과의원", 37.4970, 127.0250))],
        "강남구": [nmc_xml(("G1", "강남내과의원", 37.4985, 127.0300))],
    }

    body = get(client).json()

    assert [h["name"] for h in body["items"]] == ["강남내과의원", "서초내과의원"]  # by distance
    assert sorted(c["params"]["Q1"] for c in fake_http.nmc_calls()) == ["강남구", "서초구"]
    assert body["region"] == {"sido": "서울특별시", "sigungu": "서초구"}  # the point's own 구


def test_same_nmc_district_is_fetched_once_and_not_duplicated(client, fake_http):
    """수원시 장안구 and 수원시 팔달구 both map to NMC Q1=수원시."""
    fake_http.kakao_for = lambda lat, lng: kakao_region(
        "경기도", "수원시 장안구" if lat >= 37.4979 else "수원시 팔달구"
    )
    fake_http.nmc_by_q1 = {"수원시": [nmc_xml(("W1", "수원내과의원", 37.4980, 127.0277))]}

    body = get(client).json()

    assert len(fake_http.nmc_calls()) == 1
    assert [h["hospital_id"] for h in body["items"]] == ["W1"]


def test_ring_points_at_sea_are_ignored(client, fake_http):
    sea = fixture("kakao_sea.json")
    fake_http.kakao_for = lambda lat, lng: (
        fixture("kakao_gangnam.json") if (lat, lng) == (37.4979, 127.0276) else sea
    )

    res = get(client)

    assert res.status_code == 200
    assert {c["params"]["Q1"] for c in fake_http.nmc_calls()} == {"강남구"}


def test_ring_point_failure_does_not_fail_the_search(client, fake_http, monkeypatch):
    real_region_of = service.kakao.region_of

    def flaky(lat, lng):
        if (lat, lng) != (37.4979, 127.0276):
            raise SourceUnavailable("kakao", "timeout")
        return real_region_of(lat, lng)

    monkeypatch.setattr(service.kakao, "region_of", flaky)
    assert get(client).status_code == 200


def test_clinic_returned_by_two_districts_is_listed_once(client, fake_http):
    fake_http.kakao_for = lambda lat, lng: kakao_region(
        "서울특별시", "서초구" if lng < 127.03 else "강남구"
    )
    same = nmc_xml(("X1", "경계내과의원", 37.4980, 127.0277))
    fake_http.nmc_by_q1 = {"서초구": [same], "강남구": [same]}

    assert [h["hospital_id"] for h in get(client).json()["items"]] == ["X1"]
