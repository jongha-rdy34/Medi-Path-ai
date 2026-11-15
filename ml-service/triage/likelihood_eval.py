"""Choose the likelihood label thresholds shown instead of percentages.

A screen item is "high" if its model probability >= high, "medium" if >= medium, else "low"
(backend/triage/service.py `likelihood`). Labels use the raw probability, before the rare-disease
weight. This reports, per candidate pair, how ranks 1-3 of the on-screen Top-3 split into labels
and how often an item with each label is the true disease. No API calls.

Usage (from ml-service/, needs data/raw and the default model file):
    python -m triage.likelihood_eval --out ../docs/perf/likelihood-labels.json \
        llm/eval/results/gemini-3.5-flash-lite.json [more results files ...]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from triage.data import dedupe, group_split, load_label_map, load_one_hot_csv, make_short_set
from triage.model import TriageModel
from triage.rare_weight_eval import MAPPINGS, _ids, screen_top3
from triage.train import DEFAULT_PATHS, DEFAULT_VERSION, MODELS_DIR

CANDIDATES = ((0.5, 0.15), (0.6, 0.2), (0.7, 0.2), (0.8, 0.3))
RARE_WEIGHT = 0.5  # RARE_DISEASE_WEIGHT, user-confirmed 2026-11-15


def label(p: float, high: float, medium: float) -> str:
    return "high" if p >= high else "medium" if p >= medium else "low"


def evaluate(shown_sets: list[tuple[list[tuple[str, float]], str]], high: float, medium: float):
    ranks = [{"high": 0, "medium": 0, "low": 0} for _ in range(3)]
    hits = {"high": [0, 0], "medium": [0, 0], "low": [0, 0]}  # [true disease, items]
    for shown, truth in shown_sets:
        for i, (d, p) in enumerate(shown):
            lab = label(p, high, medium)
            ranks[i][lab] += 1
            hits[lab][1] += 1
            hits[lab][0] += d == truth
    n = len(shown_sets)
    return {
        "cases": n,
        **{f"rank{i + 1}": {k: round(v / n, 3) for k, v in r.items()} for i, r in enumerate(ranks)},
        "is_true_disease": {k: f"{a}/{b}" for k, (a, b) in hits.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare likelihood label thresholds")
    parser.add_argument("results", nargs="*", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    model = TriageModel.load(MODELS_DIR / f"{DEFAULT_VERSION}.joblib")
    rare = _ids(MAPPINGS / "rare_in_korea.csv")
    hidden = _ids(MAPPINGS / "sensitive_diseases.csv")
    rows = load_one_hot_csv(
        DEFAULT_PATHS["training_csv"], load_label_map(DEFAULT_PATHS["disease_department_csv"])
    )
    _, _, test = group_split(dedupe(rows), seed=args.seed)
    sets = {"short_test": [(sorted(s), d) for s, d in make_short_set(test, seed=args.seed)]}
    for path in args.results:
        run = json.loads(path.read_text(encoding="utf-8"))
        sets[f"e2e:{path.stem}"] = [
            ([s["symptom_id"] for s in c["extraction"]["symptoms"]], c["disease_id"])
            for c in run["cases"]
            if c["extraction"]["symptoms"]
        ]
    shown = {
        name: [
            (screen_top3(model.predict(ids, top_k=10)[0], rare, hidden, RARE_WEIGHT), truth)
            for ids, truth in cases
        ]
        for name, cases in sets.items()
    }
    report = {"model": model.version, "rare_weight": RARE_WEIGHT, "candidates": {}}
    for high, medium in CANDIDATES:
        report["candidates"][f"high>={high},medium>={medium}"] = {
            name: evaluate(s, high, medium) for name, s in shown.items()
        }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
