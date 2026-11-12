"""NMC and Kakao clients against fixtures (no real API calls)."""

import pytest

from hospitals import kakao, nmc
from hospitals.http import SourceUnavailable
from hospitals.tests.conftest import fixture


# --- NMC -----------------------------------------------------------------
def test_nmc_reads_every_page(fake_http):
    items = nmc.fetch_region("서울특별시", "강남구", "D001")

    assert [i["hpid"] for i in items] == ["T0000001", "T0000002", "T0000003", "T0000004"]
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
