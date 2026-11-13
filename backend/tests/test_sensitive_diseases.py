"""Sensitive diseases (data/mappings/sensitive_diseases.csv) are hidden from the
user-facing Top-3 and the explanation, but still count toward the department."""

import json
import logging

import pytest

from tests.contract import validate
from triage import clients, service
from triage.models import TriageSession

pytestmark = pytest.mark.django_db

# Real baseline model output (top 10) for high_fever, cough, phlegm, breathlessness.
REAL_TOP10 = [
    ("bronchial_asthma", 0.358491),
    ("aids", 0.079275),
    ("pneumonia", 0.068704),
    ("impetigo", 0.035068),
    ("heart_attack", 0.02892),
    ("gerd", 0.024678),
    ("tuberculosis", 0.020719),
    ("urinary_tract_infection", 0.019884),
    ("acne", 0.018266),
    ("gastroenteritis", 0.017563),
]
SYMPTOMS = [{"symptom_id": s} for s in ("high_fever", "cough", "phlegm", "breathlessness")]


class FixedML:
    def __init__(self, ranked):
        self.ranked = ranked

    def predict(self, symptom_ids, top_k=3):
        return "baseline-test", self.ranked[:top_k]


class SpyLLM(clients.StubLLMClient):
    def __init__(self):
        self.explained = []

    def explain(self, disease_names, symptom_ids, emergency=False):
        self.explained.append(list(disease_names))
        return "설명"


@pytest.fixture
def spy(monkeypatch):
    llm = SpyLLM()
    monkeypatch.setattr(clients, "llm_client", llm)
    return llm


def result_for(monkeypatch, ranked):
    monkeypatch.setattr(clients, "ml_client", FixedML(ranked))
    session = TriageSession.objects.create(symptoms=SYMPTOMS)
    return service.build_result(session)


def test_hidden_disease_is_replaced_by_the_next_rank(monkeypatch, spy):
    result = result_for(monkeypatch, REAL_TOP10)

    ids = [p["disease_id"] for p in result["predictions"]]
    assert ids == ["bronchial_asthma", "pneumonia", "impetigo"]
    validate(result, "TriageResult")


def test_hidden_disease_leaks_nowhere(monkeypatch, spy, caplog):
    with caplog.at_level(logging.DEBUG):
        result = result_for(monkeypatch, REAL_TOP10)

    text = json.dumps(result, ensure_ascii=False)
    assert "aids" not in text and "후천성면역결핍증" not in text
    assert spy.explained == [["기관지 천식", "폐렴", "농가진"]]
    assert "aids" not in caplog.text and "후천성" not in caplog.text


def test_department_scores_include_hidden_diseases(monkeypatch, spy):
    # Hidden aids (01) pushes internal medicine above dermatology (14);
    # without it, dermatology would win.
    ranked = [("acne", 0.30), ("psoriasis", 0.10), ("aids", 0.35), ("pneumonia", 0.10)]

    result = result_for(monkeypatch, ranked)

    assert [p["disease_id"] for p in result["predictions"]] == ["acne", "psoriasis", "pneumonia"]
    assert result["recommended_departments"][0]["code"] == "01"
    assert service.department_scores(ranked)["01"] == pytest.approx(0.45)
    assert "aids" not in json.dumps(result)


def test_department_scores_are_the_same_before_and_after_hiding(monkeypatch, spy):
    result = result_for(monkeypatch, REAL_TOP10)

    best = max(service.department_scores(REAL_TOP10).items(), key=lambda kv: kv[1])[0]
    assert result["recommended_departments"][0]["code"] == best == "01"
