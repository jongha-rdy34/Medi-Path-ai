"""Shared helpers: fixtures on disk and a fake HTTP layer (no real API calls in tests)."""

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
        self.error: Exception | None = None

    def __call__(self, url, params, headers=None, timeout=None):
        query = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        query.update({k: str(v) for k, v in params.items()})
        self.calls.append({"url": url, "params": query, "headers": headers or {}})
        if self.error:
            raise self.error
        if "kakao" in url:
            return self.kakao
        pages = self.nmc_by_q1.get(query.get("Q1", ""), self.nmc_pages)
        return pages[int(query.get("pageNo", 1)) - 1]

    def nmc_calls(self):
        return [c for c in self.calls if "data.go.kr" in c["url"]]


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
