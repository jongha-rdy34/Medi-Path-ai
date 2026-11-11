"""End-to-end evaluation: Korean sentence -> LLM extraction (T13) -> classifier (T14).

Reuses the saved LLM outputs in llm/eval/results/<model>.json, so it makes no
API calls. Usage (from ml-service/):
    python -m triage.e2e llm/eval/results/gemini-3.5-flash-lite.json

Department accuracy: the primary department of the top-1 predicted disease
equals that of the true disease (data/mappings/disease_department.csv).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from triage.model import TriageModel
from triage.train import DEFAULT_PATHS, DEFAULT_VERSION, MODELS_DIR


def load_primary_departments(
    path: Path = DEFAULT_PATHS["disease_department_csv"],
) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as f:
        return {r["disease_id"]: r["department_code"] for r in csv.DictReader(f)}


def evaluate_e2e(model: TriageModel, cases: list[dict], departments: dict[str, str]) -> dict:
    top1 = top3 = dept = empty = 0
    for c in cases:
        ids = [s["symptom_id"] for s in c["extraction"]["symptoms"]]
        if not ids:
            empty += 1
            continue
        preds = [d for d, _ in model.predict(ids, top_k=3)[0]]
        top1 += preds[0] == c["disease_id"]
        top3 += c["disease_id"] in preds
        dept += departments.get(preds[0]) == departments.get(c["disease_id"])
    n = len(cases)
    return {
        "cases": n,
        "no_symptoms_extracted": empty,
        "top1": round(top1 / n, 4),
        "top3": round(top3 / n, 4),
        "department_top1": round(dept / n, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="End-to-end evaluation from saved LLM results")
    parser.add_argument("results", type=Path)
    parser.add_argument("--model-version", default=DEFAULT_VERSION)
    args = parser.parse_args()

    run = json.loads(args.results.read_text(encoding="utf-8"))
    model = TriageModel.load(MODELS_DIR / f"{args.model_version}.joblib")
    metrics = evaluate_e2e(model, run["cases"], load_primary_departments())
    report = {"llm_model": run["model"], "classifier": model.version, **metrics}
    out = args.results.with_suffix(".e2e.json")
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
