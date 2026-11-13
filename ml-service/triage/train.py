"""Train and evaluate the baseline model (T14).

Usage (from ml-service/):
    python -m triage.train                      # writes models/<version>.joblib and .metrics.json
    python -m triage.train --version baseline-2026.11.0
    python -m triage.train --augment dropout --version dropout-2026.11.0   # T30 follow-up C-2

Needs the Kaggle raw data: python data/scripts/download.py (repository root).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from triage.data import (
    augment_with_dropout,
    dedupe,
    group_split,
    load_label_map,
    load_one_hot_csv,
    load_vocab,
    make_noise_set,
    make_short_set,
)
from triage.model import TriageModel, top_k_accuracy

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PATHS = {
    "training_csv": REPO / "data/raw/kaggle_disease_prediction/Training.csv",
    "disease_department_csv": REPO / "data/mappings/disease_department.csv",
    "symptoms_csv": REPO / "data/mappings/symptoms.csv",
}
DEFAULT_VERSION = "baseline-2026.11.0"
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"


def train_and_evaluate(
    training_csv: Path,
    disease_department_csv: Path,
    symptoms_csv: Path,
    version: str,
    seed: int,
    augment: str | None = None,
) -> dict:
    """augment=None: baseline. augment="dropout": train on train+val plus seeded symptom-dropout
    copies (T30 follow-up C-2). Evaluation sets are the same either way."""
    rows = load_one_hot_csv(training_csv, load_label_map(disease_department_csv))
    vocab = load_vocab(symptoms_csv)
    unique = dedupe(rows)
    train, val, test = group_split(unique, seed=seed)
    noise = make_noise_set(test, vocab, seed=seed)
    short = make_short_set(test, seed=seed)

    fit_rows = train + val
    if augment == "dropout":
        fit_rows = augment_with_dropout(fit_rows, seed=seed)
    elif augment is not None:
        raise ValueError(f"unknown augment: {augment}")
    model = TriageModel.fit(fit_rows, vocab, version=version)

    def scores(part):
        return {
            "rows": len(part),
            "top1": round(top_k_accuracy(model, part, 1), 4),
            "top3": round(top_k_accuracy(model, part, 3), 4),
        }

    split_sets = [{r[0] for r in p} for p in (train, val, test)]
    return {
        "model": model,
        "split": {
            "rows_in_csv": len(rows),
            "unique_combinations": len(unique),
            "train": len(train),
            "val": len(val),
            "test": len(test),
            "overlap": len(split_sets[0] & split_sets[2])
            + len(split_sets[1] & split_sets[2])
            + len(split_sets[0] & split_sets[1]),
            "testing_csv_used": False,
            "seed": seed,
            "augment": augment,
            "train_rows_after_augment": len(fit_rows),
        },
        "metrics": {
            "val": scores(val),
            "group_test": scores(test),
            "noise_test": scores(noise),
            "short_test": scores(short),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the baseline triage model")
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=MODELS_DIR)
    parser.add_argument("--augment", choices=["dropout"], default=None)
    args = parser.parse_args()

    report = train_and_evaluate(
        **DEFAULT_PATHS, version=args.version, seed=args.seed, augment=args.augment
    )
    path = report.pop("model").save(args.out)
    metrics_path = args.out / f"{args.version}.metrics.json"
    metrics_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"model: {path}\nmetrics: {metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
