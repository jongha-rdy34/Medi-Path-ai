"""Diseases rare in Korea (data/mappings/rare_in_korea.csv): ranked lower on screen with a
configurable weight and shown with a short note. Probabilities and the department stay as is."""

import pytest

from tests.contract import validate
from tests.test_sensitive_diseases import SpyLLM, result_for
from triage import clients, service

pytestmark = pytest.mark.django_db

# Real dropout-2026.11.0 output (top 10).
MILD_FEVER_HEADACHE_MUSCLE_PAIN = [
    ("malaria", 0.3754),
    ("hepatitis_a", 0.3188),
    ("chicken_pox", 0.0845),
    ("dengue", 0.0574),
    ("hypertension", 0.0219),
    ("common_cold", 0.0201),
    ("paralysis_brain_hemorrhage", 0.019),
    ("migraine", 0.0169),
    ("bppv", 0.013),
    ("tuberculosis", 0.0105),
]
HIGH_FEVER_HEADACHE_MUSCLE_PAIN = [
    ("malaria", 0.888),
    ("dengue", 0.0533),
    ("common_cold", 0.0111),
    ("typhoid", 0.0049),
    ("chicken_pox", 0.0048),
    ("impetigo", 0.004),
    ("hypertension", 0.0037),
    ("bronchial_asthma", 0.0034),
    ("paralysis_brain_hemorrhage", 0.0033),
    ("aids", 0.0033),
]


@pytest.fixture
def spy(monkeypatch):
    llm = SpyLLM()
    monkeypatch.setattr(clients, "llm_client", llm)
    return llm


def ids(result):
    return [p["disease_id"] for p in result["predictions"]]


def test_rare_disease_is_not_first_on_screen_when_the_gap_is_small(monkeypatch, spy, settings):
    settings.RARE_DISEASE_WEIGHT = 0.3

    result = result_for(monkeypatch, MILD_FEVER_HEADACHE_MUSCLE_PAIN)

    assert ids(result) == ["hepatitis_a", "malaria", "chicken_pox"]
    validate(result, "TriageResult")


def test_probabilities_are_the_model_values(monkeypatch, spy, settings):
    settings.RARE_DISEASE_WEIGHT = 0.3

    result = result_for(monkeypatch, MILD_FEVER_HEADACHE_MUSCLE_PAIN)

    shown = {p["disease_id"]: p["probability"] for p in result["predictions"]}
    assert shown["malaria"] == 0.3754 and shown["hepatitis_a"] == 0.3188


def test_rare_disease_left_on_screen_carries_a_note(monkeypatch, spy, settings):
    # 0.888 vs 0.011: no weight in 0.2-0.5 moves malaria down, so the note has to do the work.
    settings.RARE_DISEASE_WEIGHT = 0.3

    result = result_for(monkeypatch, HIGH_FEVER_HEADACHE_MUSCLE_PAIN)

    notes = {p["disease_id"]: p.get("note") for p in result["predictions"]}
    assert ids(result)[0] == "malaria"
    assert "휴전선" in notes["malaria"] and "해외여행" in notes["malaria"]
    assert "해외여행" in notes["dengue"]
    assert notes["common_cold"] is None
    validate(result, "TriageResult")


@pytest.mark.parametrize(
    "ranked", [MILD_FEVER_HEADACHE_MUSCLE_PAIN, HIGH_FEVER_HEADACHE_MUSCLE_PAIN]
)
@pytest.mark.parametrize("weight", [0.2, 0.3, 0.5, 1.0])
def test_department_is_the_same_whatever_the_weight(monkeypatch, spy, settings, ranked, weight):
    settings.RARE_DISEASE_WEIGHT = weight

    result = result_for(monkeypatch, ranked)

    best = max(service.department_scores(ranked).items(), key=lambda kv: kv[1])[0]
    assert result["recommended_departments"][0]["code"] == best


def test_weight_one_keeps_the_model_order(monkeypatch, spy, settings):
    settings.RARE_DISEASE_WEIGHT = 1.0

    result = result_for(monkeypatch, MILD_FEVER_HEADACHE_MUSCLE_PAIN)

    assert ids(result) == ["malaria", "hepatitis_a", "chicken_pox"]


def test_explanation_uses_the_screen_order(monkeypatch, spy, settings):
    settings.RARE_DISEASE_WEIGHT = 0.3

    result_for(monkeypatch, MILD_FEVER_HEADACHE_MUSCLE_PAIN)

    assert spy.explained == [["A형 간염", "말라리아", "수두"]]
