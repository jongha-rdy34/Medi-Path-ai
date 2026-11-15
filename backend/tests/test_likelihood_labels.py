"""Users see likelihood labels, not percentages (2026-11-15), and a one-line notice only when
diseases rare in Korea changed the on-screen order."""

import json

import pytest

from tests.contract import validate
from tests.test_rare_diseases import MILD_FEVER_HEADACHE_MUSCLE_PAIN
from tests.test_sensitive_diseases import REAL_TOP10, result_for
from triage import clients, service

pytestmark = pytest.mark.django_db

# Illustrative ranking like the knee demo sentence ("무릎이 붓고 걸을 때 아파요"): no rare disease.
KNEE = [("osteoarthritis", 0.52), ("arthritis", 0.31), ("varicose_veins", 0.05)]


class LabelSpyLLM(clients.StubLLMClient):
    def __init__(self, reply="설명"):
        self.calls = []
        self.reply = reply

    def explain(self, disease_names, symptom_ids, emergency=False, likelihoods=None):
        self.calls.append((list(disease_names), likelihoods))
        return self.reply


@pytest.fixture
def spy(monkeypatch):
    llm = LabelSpyLLM()
    monkeypatch.setattr(clients, "llm_client", llm)
    return llm


@pytest.mark.parametrize(
    ("p", "label"),
    [
        (0.95, "high"),
        (0.7, "high"),
        (0.6999, "medium"),
        (0.2, "medium"),
        (0.1999, "low"),
        (0.0, "low"),
    ],
)
def test_label_boundaries(settings, p, label):
    settings.LIKELIHOOD_HIGH, settings.LIKELIHOOD_MEDIUM = 0.7, 0.2

    assert service.likelihood(p) == label


def test_labels_use_the_raw_probability_not_the_rare_weight(monkeypatch, spy, settings):
    settings.RARE_DISEASE_WEIGHT = 0.5

    result = result_for(monkeypatch, MILD_FEVER_HEADACHE_MUSCLE_PAIN)

    labels = {p["disease_id"]: p["likelihood"] for p in result["predictions"]}
    # malaria 0.3754 x 0.5 would be 0.19 (low); the label follows 0.3754.
    assert labels == {"hepatitis_a": "medium", "malaria": "medium", "chicken_pox": "low"}
    validate(result, "TriageResult")


def test_order_adjusted_only_when_rare_diseases_changed_the_order(monkeypatch, spy, settings):
    settings.RARE_DISEASE_WEIGHT = 0.5

    assert result_for(monkeypatch, MILD_FEVER_HEADACHE_MUSCLE_PAIN)["order_adjusted"] is True
    assert result_for(monkeypatch, KNEE)["order_adjusted"] is False


def test_hiding_a_sensitive_disease_does_not_count_as_an_adjustment(monkeypatch, spy):
    # REAL_TOP10 has aids at rank 2 (hidden); no rare disease involved.
    result = result_for(monkeypatch, REAL_TOP10)

    assert result["order_adjusted"] is False
    assert "aids" not in json.dumps(result)


def test_explanation_gets_labels_not_numbers(monkeypatch, spy, settings):
    settings.RARE_DISEASE_WEIGHT = 0.5

    result_for(monkeypatch, MILD_FEVER_HEADACHE_MUSCLE_PAIN)

    assert spy.calls == [(["A형 간염", "말라리아", "수두"], ["medium", "medium", "low"])]


@pytest.mark.parametrize(
    "reply", ["말라리아 가능성이 38%입니다.", "확률은 37.5 %로 높습니다.", "50퍼센트 정도"]
)
def test_explanation_with_a_percentage_is_replaced(monkeypatch, settings, reply):
    monkeypatch.setattr(clients, "llm_client", LabelSpyLLM(reply))

    explanation = result_for(monkeypatch, KNEE)["explanation"]

    assert explanation == service.FALLBACK_EXPLANATION
