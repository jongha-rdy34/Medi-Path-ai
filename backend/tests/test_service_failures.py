"""How the conversation behaves when ml-service or the LLM is down (T30)."""

import json
import logging

import pytest

from tests.contract import validate
from triage import clients, service
from triage.http_clients import ServiceUnavailable
from triage.models import TriageSession

pytestmark = pytest.mark.django_db
SESSIONS = "/api/triage/sessions"


def send(client, sid, text):
    return client.post(
        f"{SESSIONS}/{sid}/messages",
        data=json.dumps({"text": text}),
        content_type="application/json",
    )


class DownLLM(clients.StubLLMClient):
    def extract_symptoms(self, text):
        raise ServiceUnavailable("llm_unavailable")


class QuietLLM(clients.StubLLMClient):
    def next_questions(self, symptom_ids):
        raise ServiceUnavailable("llm_unavailable")

    def explain(self, disease_names, symptom_ids, emergency=False):
        raise ServiceUnavailable("llm_unavailable")


def test_extraction_failure_asks_to_retry_and_keeps_the_session(client, monkeypatch, caplog):
    monkeypatch.setattr(clients, "llm_client", DownLLM())
    sid = client.post(SESSIONS).json()["session_id"]

    with caplog.at_level(logging.INFO):
        res = send(client, sid, "어제 회사에서 열이 나요")

    assert res.status_code == 503
    validate(res.json(), "Error")
    assert res.json()["code"] == "llm_unavailable" and "다시" in res.json()["message"]
    session = TriageSession.objects.get(pk=sid)
    assert session.turns == 0 and session.symptoms == [] and session.status == "collecting"
    assert "llm_unavailable" in caplog.text and "회사" not in caplog.text


def test_ml_service_down_is_503_too(client, monkeypatch):
    class DownSafety:
        def check(self, symptoms):
            raise ServiceUnavailable("service_unavailable")

    monkeypatch.setattr(clients, "safety_client", DownSafety())
    sid = client.post(SESSIONS).json()["session_id"]

    res = send(client, sid, "열이 나요")

    assert res.status_code == 503 and res.json()["code"] == "service_unavailable"
    assert TriageSession.objects.get(pk=sid).turns == 0


def test_question_and_explanation_failures_fall_back_to_fixed_text(client, monkeypatch):
    monkeypatch.setattr(clients, "llm_client", QuietLLM())
    sid = client.post(SESSIONS).json()["session_id"]

    first = send(client, sid, "열이 나요").json()
    assert first["status"] == "needs_more_info" and first["questions"] == service.FALLBACK_QUESTIONS

    send(client, sid, "기침도 나요")
    result = client.get(f"{SESSIONS}/{sid}/result").json()
    validate(result, "TriageResult")
    assert result["explanation"] == service.FALLBACK_EXPLANATION
