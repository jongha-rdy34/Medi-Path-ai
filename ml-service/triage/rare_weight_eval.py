"""Choose RARE_DISEASE_WEIGHT: how the on-screen Top-3 changes when diseases rare in Korea
(data/mappings/rare_in_korea.csv) are ranked with probability x weight.

Mirrors backend/triage/service.py `screen_top3` (sensitive diseases hidden, rare ones weighted,
model probabilities and departments unchanged). No API calls: uses the 2-3 symptom set and the
saved LLM extractions.

Usage (from ml-service/, needs data/raw and the default model file):
    python -m triage.rare_weight_eval --out ../docs/perf/rare-disease-weight.json \
        llm/eval/results/gemini-3.5-flash-lite.json [more results files ...]
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from triage.compare import EXAMPLES
from triage.data import dedupe, group_split, load_label_map, load_one_hot_csv, make_short_set
from triage.model import TriageModel
from triage.train import DEFAULT_PATHS, DEFAULT_VERSION, MODELS_DIR, REPO

MAPPINGS = REPO / "data" / "mappings"
WEIGHTS = (1.0, 0.5, 0.3, 0.2)


def screen_top3(
    ranked: list[tuple[str, float]], rare: set[str], hidden: set[str], weight: float
) -> list[tuple[str, float]]:
    candidates = [(d, p) for d, p in ranked if d not in hidden]
    return sorted(
        candidates, key=lambda dp: dp[1] * (weight if dp[0] in rare else 1.0), reverse=True
    )[:3]


def _ids(path: Path) -> set[str]:
    with path.open(encoding="utf-8", newline="") as f:
        return {r["disease_id"] for r in csv.DictReader(f)}


def evaluate(model, cases: list[tuple[list[str], str]], rare, hidden, weight) -> dict:
    """cases: (symptom ids, true disease). Cases whose truth is hidden are skipped (never shown)."""
    n = top1 = top3 = rare_first_wrong = rare_truth = rare_truth_top3 = 0
    for ids, truth in cases:
        if truth in hidden or not ids:
            continue
        shown = [d for d, _ in screen_top3(model.predict(ids, top_k=10)[0], rare, hidden, weight)]
        n += 1
        top1 += shown[0] == truth
        top3 += truth in shown
        if truth in rare:
            rare_truth += 1
            rare_truth_top3 += truth in shown
        elif shown[0] in rare:
            rare_first_wrong += 1
    return {
        "cases": n,
        "top1": round(top1 / n, 4),
        "top3": round(top3 / n, 4),
        "rare_first_when_not_rare": rare_first_wrong,
        "rare_truth_in_top3": f"{rare_truth_top3}/{rare_truth}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare RARE_DISEASE_WEIGHT values")
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
        ]
    examples = [ids for spec in EXAMPLES.values() for ids in spec["inputs"]]

    report = {"model": model.version, "rare": sorted(rare), "weights": {}}
    for w in WEIGHTS:
        report["weights"][str(w)] = {
            **{name: evaluate(model, cases, rare, hidden, w) for name, cases in sets.items()},
            "examples": [
                {
                    "symptoms": ids,
                    "screen_top3": [
                        d for d, _ in screen_top3(model.predict(ids, top_k=10)[0], rare, hidden, w)
                    ],
                }
                for ids in examples
            ],
        }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
