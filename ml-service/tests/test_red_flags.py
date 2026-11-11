"""T15: red-flag rules. Emergency recall on the case table must be 100%."""

import csv
from pathlib import Path

import pytest
import yaml

from safety.red_flags import RULES_PATH, Observation, check, load_rules
from triage.data import RISK_FACTORS

CASES = yaml.safe_load((Path(RULES_PATH).parent / "cases.yaml").read_text(encoding="utf-8"))
SYMPTOMS_CSV = Path(__file__).resolve().parents[2] / "data" / "mappings" / "symptoms.csv"


def obs(case):
    return [Observation(s["symptom_id"], s.get("severity")) for s in case["symptoms"]]


def test_emergency_recall_is_100_percent():
    emergencies = [c for c in CASES if c["expect_emergency"]]
    missed = [c["name"] for c in emergencies if not check(obs(c)).is_emergency]

    assert len(emergencies) >= 20
    assert missed == [], f"recall {1 - len(missed) / len(emergencies):.2%}, missed: {missed}"


@pytest.mark.parametrize(
    "case", [c for c in CASES if not c["expect_emergency"]], ids=lambda c: c["name"]
)
def test_non_emergency_cases_do_not_fire(case):
    assert check(obs(case)).is_emergency is False


def test_every_rule_is_covered_by_an_emergency_case():
    fired = {r for c in CASES if c["expect_emergency"] for r in check(obs(c)).rule_ids}

    assert fired == {r.id for r in load_rules()}


def test_rules_use_known_symptoms_have_sources_and_no_risk_factors():
    with SYMPTOMS_CSV.open(encoding="utf-8") as f:
        known = {r["symptom_id"] for r in csv.DictReader(f)}
    for rule in load_rules():
        assert rule.symptom_ids() <= known, rule.id
        assert not rule.symptom_ids() & set(RISK_FACTORS), rule.id
        assert rule.source and rule.reason_ko, rule.id


def test_result_carries_korean_reasons_and_119_guidance():
    result = check([Observation("chest_pain"), Observation("breathlessness")])

    assert result.is_emergency and result.reasons
    assert result.call_number == "119" and "119" in result.message
    assert "진단" not in " ".join([result.message, *result.reasons])


def test_severity_condition_only_fires_when_severe():
    assert check([Observation("abdominal_pain", "mild")]).is_emergency is False
    assert check([Observation("abdominal_pain", "severe")]).is_emergency is True
