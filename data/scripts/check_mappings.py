"""Check the mapping tables in data/mappings/ (T11).

Usage (from the repository root):
    python data/scripts/check_mappings.py

Errors (exit 1):
  - IDs that are duplicated or break the contract pattern ^[a-z][a-z0-9_]*$
  - department codes missing from departments.csv
  - the same Korean synonym listed under two different symptoms
  - a disease label or symptom column in data/raw/ that has no mapping
  - a symptom_id / disease_id / department code used in contracts/*.yaml examples
    that is not in the mapping tables
Warnings: mapping rows without source_url (team review still pending).
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = DATA_DIR.parent
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

# Raw files and how labels / symptoms appear in them.
ONE_HOT_FILES = ["kaggle_disease_prediction/Training.csv", "kaggle_disease_prediction/Testing.csv"]
LIST_FILES = ["kaggle_symptom_description/dataset.csv"]  # Disease, Symptom_1..Symptom_17


@dataclass
class Mappings:
    departments: list[dict]
    diseases: list[dict]
    symptoms: list[dict]


def symptom_id_from_column(raw: str) -> str:
    """Kaggle column name -> standard symptom_id (spaces, parens, pandas dup suffix)."""
    name = re.sub(r"\.\d+$", "", raw.strip())
    name = re.sub(r"[^a-z0-9]+", "_", name.lower())
    return name.strip("_")


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_mappings(mappings_dir: Path) -> Mappings:
    return Mappings(
        departments=_read(mappings_dir / "departments.csv"),
        diseases=_read(mappings_dir / "disease_department.csv"),
        symptoms=_read(mappings_dir / "symptoms.csv"),
    )


def _split(value: str) -> list[str]:
    return [v.strip() for v in (value or "").split("|") if v.strip()]


def _duplicates(values: list[str]) -> set[str]:
    return {v for v, n in Counter(values).items() if n > 1}


def check_mappings(m: Mappings) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    codes = {d["code"] for d in m.departments}

    disease_ids = [d["disease_id"] for d in m.diseases]
    for dup in sorted(_duplicates(disease_ids)):
        errors.append(f"duplicate disease_id '{dup}'")
    for dup in sorted(_duplicates([d["kaggle_label"] for d in m.diseases if d["kaggle_label"]])):
        errors.append(f"duplicate kaggle_label '{dup}'")
    for d in m.diseases:
        did = d["disease_id"]
        if not ID_PATTERN.match(did):
            errors.append(f"disease_id '{did}' does not match {ID_PATTERN.pattern}")
        for code in [d["department_code"], *_split(d.get("alt_department_codes", ""))]:
            if code not in codes:
                errors.append(f"disease '{did}': unknown department code '{code}'")
        if not d.get("source_url", "").strip():
            warnings.append(f"disease '{did}': source_url is empty (needs team review)")

    symptom_ids = [s["symptom_id"] for s in m.symptoms]
    for dup in sorted(_duplicates(symptom_ids)):
        errors.append(f"duplicate symptom_id '{dup}'")
    owner: dict[str, str] = {}
    for s in m.symptoms:
        sid = s["symptom_id"]
        if not ID_PATTERN.match(sid):
            errors.append(f"symptom_id '{sid}' does not match {ID_PATTERN.pattern}")
        if not s["name_ko"].strip():
            errors.append(f"symptom '{sid}': name_ko is empty")
        for term in [s["name_ko"], *_split(s.get("synonyms_ko", ""))]:
            key = term.replace(" ", "")
            if key in owner and owner[key] != sid:
                errors.append(f"term '{term}' is used by both '{owner[key]}' and '{sid}'")
            owner.setdefault(key, sid)
    return errors, warnings


def check_raw_coverage(m: Mappings, raw_dir: Path) -> list[str]:
    labels = {d["kaggle_label"] for d in m.diseases}
    symptom_ids = {s["symptom_id"] for s in m.symptoms}
    errors: list[str] = []
    found = False

    def label_ok(label: str, where: str) -> None:
        if label.strip() not in labels:
            errors.append(f"{where}: disease label '{label.strip()}' has no mapping")

    def column_ok(column: str, where: str) -> None:
        sid = symptom_id_from_column(column)
        if sid and sid not in symptom_ids:
            errors.append(f"{where}: symptom '{column}' -> '{sid}' is not in symptoms.csv")

    for rel in ONE_HOT_FILES:
        path = raw_dir / rel
        if not path.exists():
            continue
        found = True
        rows = _read(path)
        for column in rows[0].keys() if rows else []:
            if column and column != "prognosis":
                column_ok(column, rel)
        for label in sorted({r["prognosis"] for r in rows}):
            label_ok(label, rel)

    for rel in LIST_FILES:
        path = raw_dir / rel
        if not path.exists():
            continue
        found = True
        rows = _read(path)
        for label in sorted({r["Disease"] for r in rows}):
            label_ok(label, rel)
        values = {v for r in rows for k, v in r.items() if k.startswith("Symptom") and v}
        for value in sorted(values):
            column_ok(value, rel)

    if not found:
        errors.append(f"no raw data under {raw_dir}; run: python data/scripts/download.py")
    return sorted(set(errors))


def check_sensitive(m: Mappings, path: Path) -> list[str]:
    """Hidden-from-users list (sensitive_diseases.csv) must name known diseases."""
    if not path.exists():
        return []
    known = {d["disease_id"] for d in m.diseases}
    return [
        f"{path.name}: unknown disease_id '{r['disease_id']}'"
        for r in _read(path)
        if r["disease_id"] not in known
    ]


# Note keys the backend knows (backend/triage/service.py RARE_NOTES).
RARE_NOTE_KEYS = ("travel", "travel_or_border")


def check_rare_in_korea(m: Mappings, path: Path) -> list[str]:
    """Rare-in-Korea list (rare_in_korea.csv): known diseases and known note keys."""
    if not path.exists():
        return []
    known = {d["disease_id"] for d in m.diseases}
    errors = []
    for r in _read(path):
        if r["disease_id"] not in known:
            errors.append(f"{path.name}: unknown disease_id '{r['disease_id']}'")
        if r["note_key"] not in RARE_NOTE_KEYS:
            errors.append(f"{path.name}: unknown note_key '{r['note_key']}'")
    return errors


NMC_CODE_PATTERN = re.compile(r"^D[0-9]{3}$")
NMC_CODES_CSV = REPO_DIR / "prototypes" / "kakao-hospital-search" / "nmc_department_codes.csv"


def check_nmc_codes(m: Mappings, nmc_table: Path) -> list[str]:
    """departments.csv `nmc_code`: format, no duplicates, present in the NMC code table.

    Empty means NMC has no matching department (search without a department filter).
    """
    if not m.departments or "nmc_code" not in m.departments[0]:
        return []
    known = {r["nmc_code"] for r in _read(nmc_table)} if nmc_table.exists() else set()
    errors, owner = [], {}
    for d in m.departments:
        code = (d.get("nmc_code") or "").strip()
        if not code:
            continue
        if not NMC_CODE_PATTERN.match(code):
            errors.append(
                f"departments.csv: department '{d['code']}' nmc_code '{code}' "
                f"does not match {NMC_CODE_PATTERN.pattern}"
            )
            continue
        if code in owner:
            errors.append(
                f"departments.csv: nmc_code '{code}' is used by both '{owner[code]}' and '{d['code']}'"
            )
        owner.setdefault(code, d["code"])
        if known and code not in known:
            errors.append(
                f"departments.csv: department '{d['code']}' nmc_code '{code}' is not in {nmc_table.name}"
            )
    return errors


def check_contract_examples(m: Mappings, contract_paths: list[Path]) -> list[str]:
    symptom_ids = {s["symptom_id"] for s in m.symptoms}
    disease_ids = {d["disease_id"] for d in m.diseases}
    codes = {d["code"] for d in m.departments}
    errors: list[str] = []
    for path in contract_paths:
        text = path.read_text(encoding="utf-8")
        for sid in sorted(set(re.findall(r"symptom_id: ([a-z0-9_]+)", text)) - symptom_ids):
            errors.append(f"{path.name}: unknown symptom_id '{sid}'")
        for did in sorted(set(re.findall(r"disease_id: ([a-z0-9_]+)", text)) - disease_ids):
            errors.append(f"{path.name}: unknown disease_id '{did}'")
        used = set(re.findall(r"code: '(\d{2})'", text))
        for listed in re.findall(r"departments: \[([^\]]*)\]", text):
            used |= set(re.findall(r"'(\d{2})'", listed))
        for code in sorted(used - codes):
            errors.append(f"{path.name}: unknown department code '{code}'")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mappings-dir", type=Path, default=DATA_DIR / "mappings")
    parser.add_argument("--raw-dir", type=Path, default=DATA_DIR / "raw")
    args = parser.parse_args()

    m = load_mappings(args.mappings_dir)
    errors, warnings = check_mappings(m)
    errors += check_raw_coverage(m, args.raw_dir)
    errors += check_sensitive(m, args.mappings_dir / "sensitive_diseases.csv")
    errors += check_rare_in_korea(m, args.mappings_dir / "rare_in_korea.csv")
    errors += check_nmc_codes(m, NMC_CODES_CSV)
    errors += check_contract_examples(m, sorted((REPO_DIR / "contracts").glob("*.yaml")))

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(
        f"departments={len(m.departments)} diseases={len(m.diseases)} "
        f"symptoms={len(m.symptoms)} errors={len(errors)} warnings={len(warnings)}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
