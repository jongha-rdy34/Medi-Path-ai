"""T30: /llm/* and /safety/check against contracts/ml-service.openapi.yaml (fake LLM)."""

import logging

import pytest
from fastapi.testclient import TestClient
from google.genai import errors

from app.main import app
from llm.provider import Extraction, Symptom
from tests.contract import validate

ML = "ml-service.openapi.yaml"


class FakeLLM:
    model = "fake-primary"

    def __init__(self, fail=None):
        self.fail = fail
        self.explained = []

    def _maybe_fail(self):
        if self.fail:
            raise self.fail

    def extract_symptoms(self, text):
        self._maybe_fail()
        return Extraction(
            symptoms=[Symptom("high_fever", None, 1), Symptom("cough")],
            emergency_suspected=False,
            served_model="fake-backup",
        )

    def next_questions(self, symptom_ids):
        self._maybe_fail()
        return [{"question_id": "q1", "text": "열은 언제부터 났나요?", "choices": ["오늘", "어제"]}]

    def explain(self, disease_names, symptom_ids):
        self._maybe_fail()
        self.explained.append(disease_names)
        return "설명입니다."


@pytest.fixture
def client():
    with TestClient(app) as c:
        app.state.llm = FakeLLM()
        yield c


def test_extract_matches_contract_and_reports_the_serving_model(client):
    res = client.post("/llm/extract", json={"text": "어제부터 열이 나고 기침해요"})

    assert res.status_code == 200
    validate(res.json(), ML, "ExtractResponse")
    assert res.json()["model"] == "fake-backup"
    assert [s["symptom_id"] for s in res.json()["symptoms"]] == ["high_fever", "cough"]


def test_questions_and_explain_match_contract(client):
    q = client.post("/llm/questions", json={"symptom_ids": ["high_fever"]})
    e = client.post("/llm/explain", json={"disease_names": ["폐렴"], "symptom_ids": ["cough"]})

    validate(q.json(), ML, "QuestionsResponse")
    validate(e.json(), ML, "ExplainResponse")


def test_safety_check_uses_the_t15_rules(client):
    res = client.post("/safety/check", json={"symptoms": [{"symptom_id": "chest_pain"}]})

    validate(res.json(), ML, "SafetyResponse")
    assert res.json()["is_emergency"] is True and res.json()["rule_ids"] == ["chest_pain"]
    calm = client.post("/safety/check", json={"symptoms": [{"symptom_id": "runny_nose"}]})
    assert calm.json()["is_emergency"] is False


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/llm/extract", {"text": "열이 나요"}),
        ("/llm/questions", {"symptom_ids": ["cough"]}),
        ("/llm/explain", {"disease_names": ["감기"], "symptom_ids": []}),
    ],
)
def test_llm_failure_returns_503_with_cause_code_only(client, caplog, path, body):
    down = errors.ServerError(
        503, {"error": {"code": 503, "message": "x", "status": "UNAVAILABLE"}}
    )
    app.state.llm = FakeLLM(fail=down)

    with caplog.at_level(logging.INFO):
        res = client.post(path, json=body)

    assert res.status_code == 503
    validate(res.json(), "openapi.yaml", "Error")
    assert res.json()["code"] == "llm_unavailable"
    assert "llm_unavailable" in caplog.text and "503" in caplog.text
    assert "열이 나요" not in caplog.text


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/llm/extract", {"text": ""}),
        ("/llm/extract", {"text": "가" * 501}),
        ("/llm/questions", {"symptom_ids": ["Bad-Id"]}),
        ("/llm/explain", {"disease_names": [], "symptom_ids": []}),
        ("/safety/check", {"symptoms": [{"symptom_id": "cough", "extra": 1}]}),
    ],
)
def test_invalid_requests_return_422(client, path, body):
    res = client.post(path, json=body)

    assert res.status_code == 422
    validate(res.json(), "openapi.yaml", "Error")


def test_raw_text_is_not_logged(client, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post("/llm/extract", json={"text": "비밀스러운 회사 이야기와 함께 열이 나요"})

    assert "비밀스러운" not in caplog.text
