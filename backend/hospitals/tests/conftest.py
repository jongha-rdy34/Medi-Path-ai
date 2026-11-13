"""Shared helpers: fixtures on disk and a fake HTTP layer (no real API calls in tests)."""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core.cache import cache

from hospitals import http

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class FakeHttp:
    """Replaces hospitals.http.get. Routes by host; records every call."""

    def __init__(self):
        self.calls: list[dict] = []
        self.kakao = fixture("kakao_gangnam.json")
        self.nmc_pages = [fixture("nmc_page1.xml"), fixture("nmc_page2.xml")]
        self.nmc_by_q1: dict[str, list[bytes]] = {}
        self.kakao_for = None  # optional (lat, lng) -> bytes, to give each point its own 구
        self.error: Exception | None = None

    def __call__(self, url, params, headers=None, timeout=None):
        query = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        query.update({k: str(v) for k, v in params.items()})
        self.calls.append({"url": url, "params": query, "headers": headers or {}})
        if self.error:
            raise self.error
        if "kakao" in url:
            if self.kakao_for:
                return self.kakao_for(float(query["y"]), float(query["x"]))
            return self.kakao
        pages = self.nmc_by_q1.get(query.get("Q1", ""), self.nmc_pages)
        return pages[int(query.get("pageNo", 1)) - 1]

    def nmc_calls(self):
        return [c for c in self.calls if "data.go.kr" in c["url"]]

    def kakao_calls(self):
        return [c for c in self.calls if "kakao" in c["url"]]


def kakao_region(sido: str, sigungu: str) -> bytes:
    doc = {"region_type": "B", "region_1depth_name": sido, "region_2depth_name": sigungu}
    return json.dumps({"documents": [doc]}, ensure_ascii=False).encode()


def nmc_xml(*clinics: tuple[str, str, float, float]) -> bytes:
    """NMC page with (hpid, name, lat, lng) clinics open Mon-Fri 09:00-18:00."""
    items = "".join(
        f"<item><hpid>{h}</hpid><dutyName>{n}</dutyName><dutyDivNam>의원</dutyDivNam>"
        f"<dutyAddr>주소</dutyAddr><wgs84Lat>{lat}</wgs84Lat><wgs84Lon>{lng}</wgs84Lon>"
        + "".join(
            f"<dutyTime{d}s>0900</dutyTime{d}s><dutyTime{d}c>1800</dutyTime{d}c>"
            for d in range(1, 6)
        )
        + "</item>"
        for h, n, lat, lng in clinics
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><response><header><resultCode>00</resultCode>'
        f"</header><body><items>{items}</items><numOfRows>1000</numOfRows><pageNo>1</pageNo>"
        f"<totalCount>{len(clinics)}</totalCount></body></response>"
    ).encode()


@pytest.fixture
def fake_http(monkeypatch):
    fake = FakeHttp()
    monkeypatch.setattr(http, "get", fake)
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "test-nmc-key")
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-kakao-key")
    return fake


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()
