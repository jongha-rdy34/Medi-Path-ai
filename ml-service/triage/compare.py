"""Baseline vs symptom-dropout model (T30 follow-up C-2).

Trains both models with the same seed and split, then compares them on the group test set, the
noise set, the new 2-3 symptom set, end-to-end from saved LLM extractions (no API calls) and a
few hand-picked short inputs. Saves the dropout model, the service default since 2026-11-13.

Usage (from ml-service/, needs data/raw):
    python -m triage.compare --out ../docs/perf/t30-symptom-dropout.json \
        llm/eval/results/gemini-3.5-flash-lite.json [more results files ...]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from triage.e2e import evaluate_e2e, load_primary_departments
from triage.train import DEFAULT_PATHS, MODELS_DIR, train_and_evaluate

BASELINE_VERSION = "baseline-2026.11.0"
DROPOUT_VERSION = "dropout-2026.11.0"
EMERGENCY_DEPARTMENT = "24"  # diseases whose primary department is emergency medicine

# Short inputs from the T30 report. "열" may come out as high_fever or mild_fever and
# "몸살" as malaise or muscle_pain, so every reading is checked.
EXAMPLES = {
    "열·기침·누런 가래 → 폐렴이 Top-3": {
        "inputs": [["mild_fever", "cough", "phlegm"], ["high_fever", "cough", "phlegm"]],
        "want_in_top3": "pneumonia",
    },
    "열·두통·몸살 → 응급 질환(뇌출혈 등)이 1위가 아님": {
        "inputs": [
            [fever, "headache", ache]
            for fever in ("high_fever", "mild_fever")
            for ache in ("malaise", "muscle_pain")
        ],
        "severe_not_top1": True,
    },
}


def check_examples(model, departments: dict[str, str]) -> dict:
    out = {}
    for name, spec in EXAMPLES.items():
        rows = []
        for ids in spec["inputs"]:
            top3 = [d for d, _ in model.predict(ids, top_k=3)[0]]
            if "want_in_top3" in spec:
                ok = spec["want_in_top3"] in top3
            else:
                ok = departments.get(top3[0]) != EMERGENCY_DEPARTMENT
            rows.append({"symptoms": ids, "top3": top3, "ok": ok})
        out[name] = {"passed": sum(r["ok"] for r in rows), "of": len(rows), "cases": rows}
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare baseline and symptom-dropout models")
    parser.add_argument("results", nargs="*", type=Path, help="saved LLM eval results (.json)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    departments = load_primary_departments()
    report = {"seed": args.seed, "models": {}}
    for version, augment in ((BASELINE_VERSION, None), (DROPOUT_VERSION, "dropout")):
        trained = train_and_evaluate(
            **DEFAULT_PATHS, version=version, seed=args.seed, augment=augment
        )
        model = trained.pop("model")
        if augment:
            model.save(MODELS_DIR)
            (MODELS_DIR / f"{version}.metrics.json").write_text(json.dumps(trained, indent=2))
        e2e = {}
        for path in args.results:
            run = json.loads(path.read_text(encoding="utf-8"))
            e2e[path.stem] = evaluate_e2e(model, run["cases"], departments)
        report["models"][version] = {
            "augment": augment,
            "train_rows": trained["split"]["train_rows_after_augment"],
            **trained["metrics"],
            "e2e": e2e,
            "examples": check_examples(model, departments),
        }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
