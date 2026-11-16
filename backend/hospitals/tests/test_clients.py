"""NMC and Kakao clients against fixtures (no real API calls)."""

import pytest

from hospitals import kakao, nmc
from hospitals.http import SourceUnavailable
from hospitals.tests.conftest import fixture


# --- NMC -----------------------------------------------------------------
def test_nmc_reads_every_page(fake_http):
    items = nmc.fetch_region("서울특별시", "강남구", "D001")

    assert [i["hpid"] for i in items] == [
        "T0000001",
        "T0000005",
        "T0000006",
        "T0000002",
        "T0000003",
        "T0000004",
    ]
    pages = [c["params"]["pageNo"] for c in fake_http.nmc_calls()]
    assert pages == ["1", "2"]


def test_nmc_sends_region_department_and_decoded_key_once(fake_http):
    nmc.fetch_region("서울특별시", "강남구", "D001")

    p = fake_http.nmc_calls()[0]["params"]
    assert (p["Q0"], p["Q1"], p["QD"]) == ("서울특별시", "강남구", "D001")
    # Decoding key passed as-is: the HTTP layer encodes it exactly once.
    assert p["serviceKey"] == "test-nmc-key"


def test_nmc_omits_optional_filters(fake_http):
    nmc.fetch_region("세종특별자치시", None, None)

    p = fake_http.nmc_calls()[0]["params"]
    assert "Q1" not in p and "QD" not in p


def test_nmc_empty_result(fake_http):
    fake_http.nmc_pages = [fixture("nmc_empty.xml")]
    assert nmc.fetch_region("서울특별시", "강남구", "D001") == []


@pytest.mark.parametrize("name", ["nmc_error_key.xml", "nmc_error_result.xml"])
def test_nmc_error_responses_raise(fake_http, name):
    fake_http.nmc_pages = [fixture(name)]
    with pytest.raises(SourceUnavailable):
        nmc.fetch_region("서울특별시", "강남구", "D001")


def test_nmc_not_xml_raises(fake_http):
    fake_http.nmc_pages = [b"<html>gateway error"]
    with pytest.raises(SourceUnavailable):
        nmc.fetch_region("서울특별시", "강남구", "D001")


def test_nmc_without_key_raises(fake_http, monkeypatch):
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY")
    with pytest.raises(SourceUnavailable):
        nmc.fetch_region("서울특별시", "강남구", "D001")
    assert fake_http.calls == []


# --- Kakao ---------------------------------------------------------------
def test_kakao_region_uses_legal_dong_entry(fake_http):
    region = kakao.region_of(37.4979, 127.0276)

    assert region == {"sido": "서울특별시", "sigungu": "강남구"}
    call = fake_http.calls[0]
    assert call["headers"]["Authorization"] == "KakaoAK test-kakao-key"
    assert (call["params"]["x"], call["params"]["y"]) == ("127.0276", "37.4979")  # x = lng


def test_kakao_two_word_sigungu_kept_whole(fake_http):
    fake_http.kakao = fixture("kakao_bundang.json")
    assert kakao.region_of(37.4027, 127.1046) == {"sido": "경기도", "sigungu": "성남시 분당구"}


def test_kakao_sea_has_no_region(fake_http):
    fake_http.kakao = fixture("kakao_sea.json")
    assert kakao.region_of(37.0, 126.0) is None


def test_kakao_sejong_has_no_sigungu(fake_http):
    fake_http.kakao = (
        b'{"documents":[{"region_type":"B","region_1depth_name":"\xec\x84\xb8\xec\xa2\x85'
        b'\xed\x8a\xb9\xeb\xb3\x84\xec\x9e\x90\xec\xb9\x98\xec\x8b\x9c","region_2depth_name":""}]}'
    )
    assert kakao.region_of(36.48, 127.289) == {"sido": "세종특별자치시", "sigungu": None}


def test_kakao_without_key_raises(fake_http, monkeypatch):
    monkeypatch.delenv("KAKAO_REST_API_KEY")
    with pytest.raises(SourceUnavailable):
        kakao.region_of(37.4979, 127.0276)


def test_kakao_bad_json_raises(fake_http):
    fake_http.kakao = b"not json"
    with pytest.raises(SourceUnavailable):
        kakao.region_of(37.4979, 127.0276)


# --- department name rule ---------------------------------------------------
@pytest.mark.parametrize(
    ("code", "name", "kind", "expected"),
    [
        ("01", "가까운내과의원", "의원", True),
        (
            "01",
            "연세가정의학과의원",
            "의원",
            True,
        ),  # 가정의학과 sees many 내과 patients (#16 review)
        ("01", "튼튼정형외과의원", "의원", False),
        ("01", "뉴민병원", "병원", False),  # 병원 needs the name too
        ("01", "서울성모병원", "종합병원", True),  # 종합병원 is kept
        ("11", "튼튼소아과의원", "의원", True),  # synonym
        ("11", "우리소아청소년과의원", "의원", True),
        ("15", "맑은비뇨기과의원", "의원", True),  # old name of 비뇨의학과
        ("03", "마음정신과의원", "의원", True),
        ("10", "예쁜여성의원", "의원", True),
        ("04", "바른외과의원", "의원", True),
        ("04", "바른정형외과의원", "의원", False),  # 외과 must not match 정형외과
        ("04", "강남성형외과의원", "의원", False),
        ("04", "서울신경외과의원", "의원", False),
        ("02", "서울신경외과의원", "의원", False),  # 신경과 is not 신경외과
        ("02", "강남신경과의원", "의원", True),
        ("09", "편한통증의학과의원", "의원", True),
        ("49", "하얀치과의원", "치과의원", True),
        ("01", "강남요양병원", "요양병원", False),
    ],
)
def test_name_matches_department(code, name, kind, expected):
    from hospitals.departments import name_matches

    assert name_matches(code, name, kind) is expected
