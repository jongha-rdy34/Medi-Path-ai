"""Opening-hours logic (T21): open now, past midnight, previous-night carry-over, night, weekend.

Times are fixed so the tests do not depend on when they run. Day numbers follow NMC
dutyTime{n}: 1=Mon ... 7=Sun, 8=holiday.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from hospitals import hours

KST = ZoneInfo("Asia/Seoul")


def item(**times):
    """NMC item with dutyTime fields, e.g. item(d1=("0900", "1800"))."""
    out = {}
    for key, (start, close) in times.items():
        n = key[1:]
        out[f"dutyTime{n}s"] = start
        out[f"dutyTime{n}c"] = close
    return out


WEEKDAYS_9_TO_6 = item(**{f"d{n}": ("0900", "1800") for n in range(1, 6)})
LATE_NIGHT_MON = item(d1=("1900", "0200"))  # Mon 19:00 -> Tue 02:00
LATE_NIGHT_SUN = item(d7=("2200", "0300"))  # Sun 22:00 -> Mon 03:00


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=KST)


# 2026-11-09 is a Monday.
@pytest.mark.parametrize(
    ("hospital", "when", "expected"),
    [
        (WEEKDAYS_9_TO_6, "2026-11-09 10:00", True),  # weekday daytime
        (WEEKDAYS_9_TO_6, "2026-11-09 09:00", True),  # opening minute counts
        (WEEKDAYS_9_TO_6, "2026-11-09 18:00", False),  # closing minute does not
        (WEEKDAYS_9_TO_6, "2026-11-09 08:59", False),
        (WEEKDAYS_9_TO_6, "2026-11-14 10:00", False),  # Saturday, no hours
        (LATE_NIGHT_MON, "2026-11-09 23:30", True),  # same day, before midnight
        (LATE_NIGHT_MON, "2026-11-10 01:00", True),  # Tue 01:00 carried over from Mon
        (LATE_NIGHT_MON, "2026-11-10 02:00", False),  # carry-over ends at close
        (LATE_NIGHT_MON, "2026-11-10 20:00", False),  # Tue has no hours of its own
        (LATE_NIGHT_SUN, "2026-11-09 01:00", True),  # Mon 01:00 carried over from Sun
    ],
)
def test_is_open_now(hospital, when, expected):
    assert hours.is_open_at(hospital, at(when)) is expected


def test_no_hours_means_unknown_not_closed():
    assert hours.is_open_at({}, at("2026-11-09 10:00")) is None


def test_closing_at_2400_is_open_until_midnight():
    h = item(d1=("0900", "2400"))
    assert hours.is_open_at(h, at("2026-11-09 23:59")) is True
    assert hours.is_open_at(h, at("2026-11-10 00:01")) is False


def test_opening_hours_list_only_has_days_with_hours():
    h = item(d1=("0900", "1800"), d6=("0930", "1300"), d8=("1000", "1400"), d2=("1900", "0200"))

    assert hours.opening_hours(h) == [
        {"day": "mon", "open": "09:00", "close": "18:00", "crosses_midnight": False},
        {"day": "tue", "open": "19:00", "close": "02:00", "crosses_midnight": True},
        {"day": "sat", "open": "09:30", "close": "13:00", "crosses_midnight": False},
        {"day": "holiday", "open": "10:00", "close": "14:00", "crosses_midnight": False},
    ]


@pytest.mark.parametrize(
    ("hospital", "expected"),
    [
        (WEEKDAYS_9_TO_6, False),
        (item(d3=("0900", "2000")), True),  # 20:00 counts
        (item(d3=("0900", "1959")), False),
        (LATE_NIGHT_MON, True),  # past midnight counts
        (item(d6=("0900", "2300")), False),  # weekend only, not a weekday
    ],
)
def test_has_night_hours(hospital, expected):
    assert hours.has_night_hours(hospital) is expected


@pytest.mark.parametrize(
    ("hospital", "expected"),
    [
        (WEEKDAYS_9_TO_6, False),
        (item(d6=("0900", "1300")), True),
        (item(d7=("1000", "1400")), True),
        (item(d8=("1000", "1400")), False),  # holiday alone is not weekend
    ],
)
def test_has_weekend_hours(hospital, expected):
    assert hours.has_weekend_hours(hospital) is expected


def test_malformed_times_are_ignored():
    h = {"dutyTime1s": "09:00", "dutyTime1c": "1800", "dutyTime2s": "", "dutyTime2c": "1800"}
    assert hours.opening_hours(h) == []
    assert hours.is_open_at(h, at("2026-11-09 10:00")) is None


def test_same_open_and_close_is_treated_as_no_hours():
    """09:00~09:00 is most likely a data error (review on #10): ignore that day, not 24 hours."""
    h = item(d1=("0900", "0900"), d2=("0900", "1800"))

    assert [d["day"] for d in hours.opening_hours(h)] == ["tue"]
    assert hours.is_open_at(h, at("2026-11-09 15:00")) is False  # Mon: ignored day
    assert hours.has_night_hours(item(d1=("0900", "0900"))) is False
    assert hours.is_open_at(item(d1=("0900", "0900")), at("2026-11-09 15:00")) is None
