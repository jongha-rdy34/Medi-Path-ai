"""심평원 진료과 코드(service-wide) → NMC 진료과목 코드(D001..), only inside backend/hospitals/.

Source of truth: data/mappings/departments.csv (data-foundation). Its `nmc_code` column is added by
the engineering agent from prototypes/kakao-hospital-search/nmc_department_codes.csv (T21 PR 1).
An empty `nmc_code` means NMC has no matching 진료과목 (e.g. 00 일반의): search without QD.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

# TODO(T21): remove once departments.csv has the nmc_code column (Issue #1 / #3).
# Until then only 내과 is mapped (handoff v2); other codes search without a department filter.
TEMPORARY_NMC_CODES = {"01": "D001"}


@dataclass(frozen=True)
class Department:
    code: str
    name: str
    nmc_code: str | None


def _load(path: Path) -> dict[str, Department]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    has_column = bool(rows) and "nmc_code" in rows[0]
    out = {}
    for r in rows:
        nmc = (
            (r.get("nmc_code") or "").strip() if has_column else TEMPORARY_NMC_CODES.get(r["code"])
        )
        out[r["code"]] = Department(r["code"], r["name_ko"], nmc or None)
    return out


_cache: dict[Path, tuple[float, dict[str, Department]]] = {}


def lookup(code: str) -> Department | None:
    """None when `code` is not in departments.csv. Re-reads the file when it changes."""
    path = Path(settings.MAPPINGS_DIR) / "departments.csv"
    mtime = path.stat().st_mtime
    cached = _cache.get(path)
    if not cached or cached[0] != mtime:
        cached = (mtime, _load(path))
        _cache[path] = cached
    return cached[1].get(code)
