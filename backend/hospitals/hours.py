"""Opening-hours logic on NMC items (T21).

NMC gives dutyTime{n}s / dutyTime{n}c as "HHMM" strings for n = 1..7 (Mon..Sun) and 8 (holiday).
Source: 국립중앙의료원 전국 병·의원 찾기 서비스 활용가이드(서비스 버전 1.1), getHsptlMdcncListInfoInqire.

A close time before the open time means the clinic runs past midnight into the next day.
Equal open and close times (e.g. 0900/0900) are treated as a data error and that day is ignored.
All times are Korea time (Asia/Seoul). Holidays are not detected (known limitation, SPEC 4.1).
"""

from __future__ import annotations

import re
from datetime import datetime

from django.conf import settings

DAYS = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 7: "sun", 8: "holiday"}
WEEKDAYS = (1, 2, 3, 4, 5)
_HHMM = re.compile(r"^([01]\d|2[0-4])([0-5]\d)$")


def night_cutoff() -> int:
    """Minutes after midnight. Weekday hours closing at or after this count as night hours."""
    hhmm = str(getattr(settings, "HOSPITALS_NIGHT_CUTOFF", "2000"))
    return _minutes(hhmm) or 20 * 60


def _minutes(hhmm: str | None) -> int | None:
    m = _HHMM.match((hhmm or "").strip())
    if not m:
        return None
    total = int(m[1]) * 60 + int(m[2])
    return total if total <= 24 * 60 else None


def _span(item: dict, day: int) -> tuple[int, int] | None:
    start = _minutes(item.get(f"dutyTime{day}s"))
    close = _minutes(item.get(f"dutyTime{day}c"))
    if start is None or close is None or start == close:
        return None
    return start, close


def _crosses_midnight(span: tuple[int, int]) -> bool:
    start, close = span
    return close < start


def _fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def opening_hours(item: dict) -> list[dict]:
    out = []
    for day, name in DAYS.items():
        span = _span(item, day)
        if span:
            out.append(
                {
                    "day": name,
                    "open": _fmt(span[0]),
                    "close": _fmt(span[1]),
                    "crosses_midnight": _crosses_midnight(span),
                }
            )
    return out


def is_open_at(item: dict, when: datetime) -> bool | None:
    """True/False at `when` (must be Korea time). None when the item has no usable hours."""
    if not any(_span(item, d) for d in DAYS):
        return None
    day = when.isoweekday()  # 1=Mon .. 7=Sun, same as NMC
    now = when.hour * 60 + when.minute

    today = _span(item, day)
    if today:
        start, close = today
        if _crosses_midnight(today):
            if now >= start:
                return True
        elif start <= now < close:
            return True

    yesterday = _span(item, 7 if day == 1 else day - 1)
    return bool(yesterday and _crosses_midnight(yesterday) and now < yesterday[1])


def has_night_hours(item: dict) -> bool:
    cutoff = night_cutoff()
    for day in WEEKDAYS:
        span = _span(item, day)
        if span and (_crosses_midnight(span) or span[1] >= cutoff):
            return True
    return False


def has_weekend_hours(item: dict) -> bool:
    return bool(_span(item, 6) or _span(item, 7))
