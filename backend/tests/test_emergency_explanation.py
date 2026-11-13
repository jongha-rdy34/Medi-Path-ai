"""T30 follow-up C-3: an emergency result only points to 119 or the ER, never a regular visit."""

import json

import pytest

from triage import clients
from triage.http_clients import ServiceUnavailable

pytestmark = pytest.mark.django_db
SESSIONS = "/api/triage/sessions"
GENERAL_VISIT_WORDS = ("병원", "의원", "내원")


def emergency_result(client):
    sid = client.post(SESSIONS).json()["session_id"]
    body = client.post(
        f"{SESSIONS}/{sid}/messages",
        data=json.dumps({"text": "가슴이 아프고 숨이 차요"}),
        content_type="application/json",
    ).json()
    assert body["emergency"] is True
    return client.get(f"{SESSIONS}/{sid}/result").json()


class RecordingLLM(clients.StubLLMClient):
    def __init__(self):
        self.flags = []

    def explain(self, disease_names, symptom_ids, emergency=False):
        self.flags.append(emergency)
        return super().explain(disease_names, symptom_ids, emergency)


class DownExplainLLM(clients.StubLLMClient):
    def explain(self, disease_names, symptom_ids, emergency=False):
        raise ServiceUnavailable("llm_unavailable")


def test_emergency_results_ask_the_llm_for_an_emergency_explanation(client, monkeypatch):
    llm = RecordingLLM()
    monkeypatch.setattr(clients, "llm_client", llm)

    emergency_result(client)

    assert llm.flags == [True]


@pytest.mark.parametrize("llm", [clients.StubLLMClient(), DownExplainLLM()])
def test_emergency_explanation_has_no_regular_visit_advice(client, monkeypatch, llm):
    monkeypatch.setattr(clients, "llm_client", llm)

    explanation = emergency_result(client)["explanation"]

    assert "119" in explanation
    assert not any(w in explanation for w in GENERAL_VISIT_WORDS)
