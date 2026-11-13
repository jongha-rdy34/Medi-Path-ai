"""T30 follow-up C-1: each Gemini call has a time limit; on timeout switch to the fallback model,
and an explanation falls back to the default sentence instead."""

import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app, load_llm
from llm.gemini import GeminiProvider, LlmTimeout
from llm.provider import EMERGENCY_EXPLANATION, FALLBACK_EXPLANATION
from tests.test_llm_provider import VOCAB, FakeModels


class TimeoutException(Exception):  # same class name as httpx / httpx2
    pass


class ReadTimeout(TimeoutException):
    pass


EXTRACT_OK = '{"symptoms": [{"symptom_id": "cough"}], "emergency_suspected": false}'


def make(*replies, timeout_s=8.0):
    from types import SimpleNamespace

    client = SimpleNamespace(models=FakeModels(replies))
    p = GeminiProvider(
        client=client,
        model="primary",
        fallback_model="backup",
        vocab=VOCAB,
        retry_sleep=0,
        timeout_s=timeout_s,
    )
    return p, client.models.calls


def test_every_call_carries_the_time_limit_in_milliseconds():
    p, calls = make(EXTRACT_OK, timeout_s=8.0)

    p.extract_symptoms("기침이 나요")

    assert calls[0]["config"].http_options.timeout == 8000


def test_server_deadline_stays_at_gemini_minimum_of_10_seconds():
    # Gemini rejects a deadline under 10 s with 400 ("Minimum allowed deadline is 10s"), and the
    # SDK derives X-Server-Timeout from the client timeout unless the header is already set.
    p, calls = make(EXTRACT_OK, timeout_s=8.0)

    p.extract_symptoms("기침이 나요")

    assert int(calls[0]["config"].http_options.headers["X-Server-Timeout"]) >= 10


def test_timeout_on_the_primary_goes_straight_to_the_fallback_model():
    p, calls = make(ReadTimeout("slow"), EXTRACT_OK)

    ex = p.extract_symptoms("기침이 나요")

    assert [c["model"] for c in calls] == ["primary", "backup"]  # no retry on the slow model
    assert ex.served_model == "backup"
    assert [s.symptom_id for s in ex.symptoms] == ["cough"]


def test_extraction_timing_out_on_both_models_raises_a_timeout():
    p, _ = make(ReadTimeout("slow"), ReadTimeout("slow"))

    with pytest.raises(LlmTimeout) as exc:
        p.extract_symptoms("기침이 나요")
    assert exc.value.code == "timeout"


@pytest.mark.parametrize(
    ("emergency", "expected"), [(False, FALLBACK_EXPLANATION), (True, EMERGENCY_EXPLANATION)]
)
def test_explanation_timeout_uses_the_default_sentence_without_the_fallback(emergency, expected):
    p, calls = make(ReadTimeout("slow"))

    text = p.explain(["감기"], ["cough"], emergency=emergency)

    assert text == expected
    assert [c["model"] for c in calls] == ["primary"]


def test_time_limit_comes_from_settings(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    monkeypatch.setenv("LLM_TIMEOUT_S", "6.5")

    assert load_llm().timeout_s == 6.5

    monkeypatch.delenv("LLM_TIMEOUT_S")
    assert load_llm().timeout_s == 8.0


def test_extract_timeout_is_a_503_that_logs_only_the_cause(caplog):
    class SlowLLM:
        model = "primary"

        def extract_symptoms(self, text):
            raise LlmTimeout()

    with TestClient(app) as c, caplog.at_level(logging.WARNING, logger="ml-service"):
        app.state.llm = SlowLLM()
        res = c.post("/llm/extract", json={"text": "비밀 문장 기침"})

    assert res.status_code == 503 and res.json()["code"] == "llm_unavailable"
    assert "cause=timeout" in caplog.text and "비밀 문장" not in caplog.text


def test_switching_to_the_fallback_is_logged_with_the_cause_only(caplog):
    p, _ = make(ReadTimeout("slow"), EXTRACT_OK)

    with caplog.at_level(logging.WARNING, logger="llm.gemini"):
        p.extract_symptoms("비밀 문장 기침")

    assert "llm_fallback from=primary to=backup cause=timeout" in caplog.text
    assert "비밀 문장" not in caplog.text


def test_explanation_still_uses_the_fallback_model_on_quota_errors():
    from google.genai import errors

    quota = errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "x"}})
    p, calls = make(quota, "감기 가능성이 있습니다.")
    p.max_retries = 1  # as in the service (app.main.load_llm)

    text = p.explain(["감기"], ["cough"])

    assert text == "감기 가능성이 있습니다."
    assert [c["model"] for c in calls][-1] == "backup"


def test_quota_error_goes_straight_to_the_fallback_without_retrying_the_same_model():
    # 429 is a per-minute quota: retrying the same model a second later only adds latency.
    from google.genai import errors

    quota = errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "x"}})
    p, calls = make(quota, EXTRACT_OK)
    p.max_retries = 1

    p.extract_symptoms("기침이 나요")

    assert [c["model"] for c in calls] == ["primary", "backup"]


def test_server_errors_are_still_retried_on_the_same_model_first():
    from google.genai import errors

    busy = errors.ServerError(503, {"error": {"code": 503, "message": "busy", "status": "x"}})
    p, calls = make(busy, EXTRACT_OK)
    p.max_retries = 1

    p.extract_symptoms("기침이 나요")

    assert [c["model"] for c in calls] == ["primary", "primary"]
