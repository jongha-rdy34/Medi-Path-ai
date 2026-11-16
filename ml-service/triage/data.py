"""Kaggle training data: loading, deduplication, group split and noise set (T14).

Evaluation rules (SPEC section 1, 2026-11-11):
- Training.csv is deduplicated and split by unique symptom combination, so the
  same combination never appears in two splits. Testing.csv is not used (41 of
  its 42 rows repeat Training.csv; see data/notebooks/eda.ipynb).
- A seeded noise set drops some symptoms and adds an unrelated one.
- Risk factors are never used as model input (SPEC section 6).
"""

from __future__ import annotations

import csv
import random
import re
from collections import defaultdict
from pathlib import Path

Row = tuple[frozenset[str], str]  # (symptom ids, disease id)

# Collection is on hold until the team decides (SPEC section 6, open question 6).
RISK_FACTORS = ("extra_marital_contacts", "receiving_unsterile_injections", "family_history")


def symptom_id_from_column(raw: str) -> str:
    """Kaggle column -> standard symptom_id. Same rule as data/scripts/check_mappings.py."""
    name = re.sub(r"\.\d+$", "", raw.strip())
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def load_one_hot_csv(path: Path, label_to_id: dict[str, str]) -> list[Row]:
    """Read a one-hot Kaggle file (symptom columns + `prognosis`) into rows."""
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        label_col = header.index("prognosis")
        columns = [
            (i, symptom_id_from_column(h)) for i, h in enumerate(header) if h and i != label_col
        ]
        rows = []
        for record in reader:
            symptoms = frozenset(sid for i, sid in columns if record[i].strip() == "1")
            rows.append((symptoms, label_to_id[record[label_col].strip()]))
    return rows


def load_label_map(disease_department_csv: Path) -> dict[str, str]:
    with disease_department_csv.open(encoding="utf-8", newline="") as f:
        return {r["kaggle_label"]: r["disease_id"] for r in csv.DictReader(f)}


def load_vocab(symptoms_csv: Path) -> list[str]:
    with symptoms_csv.open(encoding="utf-8", newline="") as f:
        return [r["symptom_id"] for r in csv.DictReader(f)]


def dedupe(rows: list[Row]) -> list[Row]:
    return list(dict.fromkeys(rows))


def group_split(
    rows: list[Row], seed: int, val_per_disease: int = 1, test_per_disease: int = 1
) -> tuple[list[Row], list[Row], list[Row]]:
    """Split unique combinations per disease into train / val / test.

    Every disease appears in every split; a combination appears in only one.
    """
    by_disease: dict[str, list[Row]] = defaultdict(list)
    for row in dedupe(rows):
        by_disease[row[1]].append(row)
    rng = random.Random(seed)
    train, val, test = [], [], []
    for disease in sorted(by_disease):
        group = sorted(by_disease[disease], key=lambda r: sorted(r[0]))
        rng.shuffle(group)
        test += group[:test_per_disease]
        val += group[test_per_disease : test_per_disease + val_per_disease]
        train += group[test_per_disease + val_per_disease :]
    return train, val, test


def make_noise_set(
    rows: list[Row],
    vocab: list[str],
    seed: int,
    variants: int = 5,
    drop_prob: float = 0.3,
    add: int = 1,
    min_symptoms: int = 2,
) -> list[Row]:
    """Per row: drop each symptom with `drop_prob` (keep at least `min_symptoms`)
    and add `add` unrelated symptoms. Risk factors are never added."""
    rng = random.Random(seed)
    candidates = sorted(set(vocab) - set(RISK_FACTORS))
    noisy = []
    for symptoms, disease in rows:
        original = sorted(symptoms)
        for _ in range(variants):
            kept = [s for s in original if rng.random() >= drop_prob]
            if len(kept) < min(min_symptoms, len(original)):
                kept = rng.sample(original, min(min_symptoms, len(original)))
            extra = rng.sample([c for c in candidates if c not in symptoms], add)
            noisy.append((frozenset(kept + extra), disease))
    return noisy


def augment_with_dropout(
    rows: list[Row],
    seed: int,
    variants: int = 10,
    drop_prob: float = 0.5,
    short_sizes: tuple[int, ...] = (2, 3),
    min_symptoms: int = 2,
) -> list[Row]:
    """Training augmentation (T30 follow-up C-2): real users name 2-3 symptoms, while a
    Kaggle combination has 7.6 on average.

    Keeps every original row and adds, per row, `variants` copies that drop each symptom with
    `drop_prob` (at least `min_symptoms` kept) plus one random subset of each size in
    `short_sizes`. Only removes symptoms, never adds one; risk factors are left out of the
    subsets (they are never model input, SPEC section 6). Seeded, so training is reproducible.
    """
    rng = random.Random(seed)
    out = list(rows)
    for symptoms, disease in rows:
        pool = sorted(symptoms - set(RISK_FACTORS))
        if len(pool) <= min_symptoms:
            continue
        for _ in range(variants):
            kept = [s for s in pool if rng.random() >= drop_prob]
            if len(kept) < min_symptoms:
                kept = rng.sample(pool, min_symptoms)
            out.append((frozenset(kept), disease))
        for size in short_sizes:
            if len(pool) > size:
                out.append((frozenset(rng.sample(pool, size)), disease))
    return out


def make_short_set(
    rows: list[Row], seed: int, sizes: tuple[int, ...] = (2, 3), per_row: int = 5
) -> list[Row]:
    """Evaluation set of 2-3 symptom inputs (T30 follow-up C-2): up to `per_row` distinct random
    subsets of each size from each held-out row. No unrelated symptoms are added (the noise set
    covers that), and risk factors are left out."""
    rng = random.Random(seed)
    out: dict[Row, None] = {}
    for symptoms, disease in rows:
        pool = sorted(symptoms - set(RISK_FACTORS))
        for size in sizes:
            if len(pool) < size:
                continue
            for _ in range(per_row):
                out[(frozenset(rng.sample(pool, size)), disease)] = None
    return list(out)
