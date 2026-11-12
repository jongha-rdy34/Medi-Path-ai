"""Minimal HTTP GET on the standard library (no new dependency, AGENTS.md 5).

Never log URLs: they carry the public-data service key and the user's coordinates.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from urllib.parse import urlencode

DEFAULT_TIMEOUT = 5.0  # seconds per request


class SourceUnavailable(Exception):
    """An upstream (NMC public data or Kakao) failed. Maps to 503 hospital_source_unavailable."""

    def __init__(self, source: str, reason: str):
        self.source = source
        self.reason = reason
        super().__init__(f"{source}: {reason}")


def get(
    url: str, params: dict, headers: dict | None = None, timeout: float = DEFAULT_TIMEOUT
) -> bytes:
    """GET url?params. Values are URL-encoded exactly once here."""
    source = "kakao" if "kakao" in url else "nmc"
    request = urllib.request.Request(f"{url}?{urlencode(params)}", headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as res:
            return res.read()
    except urllib.error.HTTPError as e:
        raise SourceUnavailable(source, f"http_{e.code}") from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise SourceUnavailable(source, type(e).__name__) from None
