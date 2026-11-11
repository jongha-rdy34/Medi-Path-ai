"""Acceptance test for T14 on the real Kaggle data (SPEC section 1).

Needs `python data/scripts/download.py` first; skipped when the raw data is absent.
"""

import pytest

from triage.train import DEFAULT_PATHS, train_and_evaluate

pytestmark = pytest.mark.skipif(
    not DEFAULT_PATHS["training_csv"].exists(),
    reason="raw data missing: run data/scripts/download.py",
)


@pytest.fixture(scope="module")
def report():
    return train_and_evaluate(**DEFAULT_PATHS, version="baseline-test", seed=42)


def test_group_split_test_set_top3_at_least_080(report):
    assert report["metrics"]["group_test"]["top3"] >= 0.80


def test_noise_test_set_top3_at_least_080(report):
    assert report["metrics"]["noise_test"]["top3"] >= 0.80


def test_splits_share_no_combination(report):
    assert report["split"]["overlap"] == 0
    assert report["split"]["testing_csv_used"] is False
