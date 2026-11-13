"""T30 follow-up C-2: symptom-dropout augmentation and the 2-3 symptom evaluation set."""

import pytest

from triage.data import RISK_FACTORS, augment_with_dropout, make_short_set
from triage.train import DEFAULT_PATHS, train_and_evaluate

ROWS = [
    (frozenset({"a", "b", "c", "d", "e", "f"}), "flu"),
    (frozenset({"g", "h", "i", "j"}), "cold"),
    (frozenset({"k", "l"}), "itch"),
]


def test_augmentation_is_seeded():
    assert augment_with_dropout(ROWS, seed=7) == augment_with_dropout(ROWS, seed=7)
    assert augment_with_dropout(ROWS, seed=7) != augment_with_dropout(ROWS, seed=8)


def test_augmentation_keeps_originals_and_only_removes_symptoms():
    out = augment_with_dropout(ROWS, seed=7)

    for row in ROWS:
        assert row in out
    by_disease = {d: s for s, d in ROWS}
    for symptoms, disease in out:
        assert symptoms <= by_disease[disease]  # never adds a symptom
        assert len(symptoms) >= 2


def test_augmentation_includes_two_and_three_symptom_samples_per_disease():
    out = augment_with_dropout(ROWS, seed=7)

    for disease in ("flu", "cold"):
        sizes = {len(s) for s, d in out if d == disease}
        assert {2, 3} <= sizes


def test_short_set_has_only_two_or_three_symptom_subsets_of_held_out_rows():
    short = make_short_set(ROWS, seed=7)

    assert short == make_short_set(ROWS, seed=7)
    by_disease = {d: s for s, d in ROWS}
    assert {len(s) for s, _ in short} == {2, 3}
    for symptoms, disease in short:
        assert symptoms <= by_disease[disease]
        assert not symptoms & set(RISK_FACTORS)
    assert len(short) == len(set(short))  # no duplicate rows


# --- on the real Kaggle data (skipped when data/raw is absent, e.g. in CI) ---

real_data = pytest.mark.skipif(
    not DEFAULT_PATHS["training_csv"].exists(),
    reason="raw data missing: run data/scripts/download.py",
)


@real_data
def test_dropout_training_reports_the_short_set_and_keeps_the_split_clean():
    report = train_and_evaluate(**DEFAULT_PATHS, version="dropout-test", seed=42, augment="dropout")

    assert report["split"]["augment"] == "dropout"
    assert report["split"]["overlap"] == 0
    assert report["split"]["train_rows_after_augment"] > report["split"]["train"]
    assert {"group_test", "noise_test", "short_test"} <= set(report["metrics"])
    assert report["metrics"]["group_test"]["top3"] >= 0.80


@real_data
def test_baseline_training_is_unchanged_without_augmentation():
    report = train_and_evaluate(**DEFAULT_PATHS, version="baseline-test", seed=42)

    assert report["split"]["augment"] is None
    assert report["metrics"]["group_test"] == {"rows": 41, "top1": 1.0, "top3": 1.0}
