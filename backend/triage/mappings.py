"""Read-only lookups from data/mappings (data-foundation, T11)."""

import csv
from functools import cache
from pathlib import Path

from django.conf import settings


def _rows(name: str) -> list[dict]:
    path = Path(settings.MAPPINGS_DIR) / name
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@cache
def diseases() -> dict[str, dict]:
    return {r["disease_id"]: r for r in _rows("disease_department.csv")}


@cache
def departments() -> dict[str, str]:
    return {r["code"]: r["name_ko"] for r in _rows("departments.csv")}
