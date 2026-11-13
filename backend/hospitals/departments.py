"""심평원 진료과 코드(service-wide) → NMC 진료과목 코드(D001..), only inside backend/hospitals/.

Source of truth: data/mappings/departments.csv (data-foundation). Its `nmc_code` column is added by
the engineering agent from prototypes/kakao-hospital-search/nmc_department_codes.csv (T21 PR 1).
An empty `nmc_code` means NMC has no matching 진료과목 (e.g. 00 일반의): search without QD.
"""

from __future__ import annotations

import csv
import re
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


# --- Department name rule (decision 2026-11-12, @ley-21) ------------------------------------
# NMC's QD returns every institution that *lists* the department, e.g. an orthopedic clinic that
# also lists 내과 (live: 서초구 내과 290건, of which 70 clinics had 내과 in the name). For a
# specialty the service should point to a clinic of that specialty, so institutions must carry
# the department in their name. 종합병원 (incl. 상급종합) is exempt: it really runs the department.
NAME_RULE_EXEMPT_TYPES = frozenset({"종합병원"})

# 심평원 code -> regex on the institution name. Default: the department name itself.
# Synonyms cover old names (비뇨기과, 소아과, 정신과) and common clinic names (여성의원, 통증).
_SURGERY_PREFIXES = ("정형", "성형", "신경", "흉부", "악안면")
NAME_PATTERNS: dict[str, str] = {
    "02": r"신경과",
    "03": r"정신건강의학과|정신과|정신의학과",
    "04": "".join(f"(?<!{p})" for p in _SURGERY_PREFIXES) + r"외과",
    "07": r"흉부외과|흉부심장혈관외과",
    "09": r"마취통증|통증의학과|통증",
    "10": r"산부인과|여성의원|여성병원",
    "11": r"소아청소년과|소아과|어린이",
    "15": r"비뇨",
    "16": r"영상의학과|영상",
    "17": r"방사선종양|치료방사선",
    "18": r"병리",
    "19": r"진단검사|임상병리",
    "21": r"재활",
    "49": r"치과",
}


def name_matches(code: str, name: str, institution_type: str) -> bool:
    """True when the institution may be shown for department `code`."""
    if (institution_type or "").strip() in NAME_RULE_EXEMPT_TYPES:
        return True
    pattern = NAME_PATTERNS.get(code)
    if pattern is None:
        dept = lookup(code)
        pattern = re.escape(dept.name) if dept else None
    return bool(pattern and re.search(pattern, name or ""))
