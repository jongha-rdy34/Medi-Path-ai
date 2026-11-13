"""T13 offline tests: GeminiProvider parsing and safety filters with a fake client."""

import json
from types import SimpleNamespace

import pytest
from google.genai import errors

from llm.gemini import GeminiProvider
from llm.provider import (
    BLOCKED_QUESTION_TERMS,
    filter_questions,
    sanitize_explanation,
)
from triage.data import RISK_FACTORS

VOCAB = {
    "high_fever": "고열",
    "cough": "기침",
    "chest_pain": "흉통",
    **{r: r for r in RISK_FACTORS},
}


class FakeModels:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        usage = SimpleNamespace(prompt_token_count=100, candidates_token_count=20)
        return SimpleNamespace(text=reply, usage_metadata=usage)


def provider(*replies):
    client = SimpleNamespace(models=FakeModels(replies))
    return GeminiProvider(client=client, model="fake-model", vocab=VOCAB, retry_sleep=0), client


def test_extract_parses_json_and_drops_unknown_and_risk_factor_ids():
    reply = json.dumps(
        {
            "symptoms": [
                {"symptom_id": "high_fever", "duration_days": 1},
                {"symptom_id": "cough", "severity": "very bad"},
                {"symptom_id": "family_history"},
                {"symptom_id": "made_up"},
            ],
            "emergency_suspected": False,
        }
    )
    p, _ = provider(reply)

    result = p.extract_symptoms("어제부터 열이 나고 기침해요")

    assert result.parsed is True
    assert [s.symptom_id for s in result.symptoms] == ["high_fever", "cough"]
    assert result.symptoms[0].duration_days == 1 and result.symptoms[1].severity is None
    assert result.prompt_tokens == 100 and result.output_tokens == 20


def test_prompt_dictionary_excludes_risk_factors_and_forbids_them():
    p, client = provider(json.dumps({"symptoms": [], "emergency_suspected": False}))
    p.extract_symptoms("text")

    config = client.models.calls[0]["config"]
    lines = config.system_instruction.splitlines()
    listed = {line.split(":")[0] for line in lines if ":" in line}
    assert {"high_fever", "cough", "chest_pain"} <= listed
    assert not listed & set(RISK_FACTORS)
    assert config.response_mime_type == "application/json"
    # Gemini rejects a symptom_id enum this large (400), so the dictionary + sanitizer enforce ids.
    props = config.response_json_schema["properties"]["symptoms"]["items"]["properties"]
    assert props["symptom_id"] == {"type": "string"}
    assert "성 접촉" in config.system_instruction and "가족력" in config.system_instruction


def test_invalid_json_counts_as_parse_failure():
    p, _ = provider("not json")

    result = p.extract_symptoms("text")

    assert result.parsed is False and result.symptoms == []


def test_rate_limit_is_retried():
    limited = errors.ClientError(
        429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
    )
    p, client = provider(
        limited, json.dumps({"symptoms": [], "emergency_suspected": True, "emergency_reason": "x"})
    )

    result = p.extract_symptoms("text")

    assert result.parsed and result.emergency_suspected and len(client.models.calls) == 2


def test_questions_about_risk_factors_or_identity_are_removed():
    questions = [
        {"question_id": "q1", "text": "열은 언제부터 났나요?"},
        {"question_id": "q2", "text": "최근 성관계가 있었나요?"},
        {"question_id": "q3", "text": "가족 중에 같은 병을 앓은 분이 있나요?"},
        {"question_id": "q4", "text": "주소를 알려 주세요"},
        {"question_id": "q5", "text": "기침에 피가 섞이나요?", "choices": ["예", "아니오"]},
        {"question_id": "q6", "text": "가래 색은 어떤가요?"},
    ]

    kept = filter_questions(questions)

    assert [q["question_id"] for q in kept] == ["q1", "q5", "q6"]
    assert {"성관계", "가족", "주소"} <= set(BLOCKED_QUESTION_TERMS) | {"가족"}


def test_next_questions_returns_at_most_three_filtered_questions():
    reply = json.dumps(
        {
            "questions": [
                {"question_id": f"q{i}", "text": t}
                for i, t in enumerate(
                    ["가족력이 있나요?", "언제부터?", "열은?", "기침은?", "가래는?"]
                )
            ]
        }
    )
    p, _ = provider(reply)

    qs = p.next_questions(["high_fever"])

    assert [q["text"] for q in qs] == ["언제부터?", "열은?", "기침은?"]


def test_explanation_never_says_diagnosis():
    assert "진단" not in sanitize_explanation("이 진단 결과에 따르면 감기 가능성이 높습니다.")


@pytest.mark.parametrize("bad", ["", "   "])
def test_explain_falls_back_when_empty(bad):
    p, _ = provider(bad)

    assert p.explain(["pneumonia"], ["high_fever"]).strip()


@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_temporary_server_errors_are_retried(code):
    overloaded = errors.ServerError(
        code, {"error": {"code": code, "message": "temporary", "status": "UNAVAILABLE"}}
    )
    p, client = provider(overloaded, json.dumps({"symptoms": [], "emergency_suspected": False}))

    assert p.extract_symptoms("text").parsed and len(client.models.calls) == 2


def test_rate_limit_backoff_is_exponential(monkeypatch):
    sleeps = []
    monkeypatch.setattr("llm.gemini.time.sleep", sleeps.append)
    limited = errors.ClientError(
        429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
    )
    client = SimpleNamespace(
        models=FakeModels(
            [limited, limited, limited, json.dumps({"symptoms": [], "emergency_suspected": False})]
        )
    )
    p = GeminiProvider(client=client, model="m", vocab=VOCAB, retry_sleep=1.0)

    p.extract_symptoms("text")

    assert sleeps == [1.0, 2.0, 4.0]


def test_latency_excludes_retry_waits(monkeypatch):
    monkeypatch.setattr("llm.gemini.time.sleep", lambda s: None)
    # attempt 1 starts at 0 s and fails; attempt 2 runs from 100 s to 101.5 s
    clock = iter([0.0, 100.0, 101.5])
    monkeypatch.setattr("llm.gemini.time.perf_counter", lambda: next(clock))
    overloaded = errors.ServerError(
        503, {"error": {"code": 503, "message": "x", "status": "UNAVAILABLE"}}
    )
    p, _ = provider(overloaded, json.dumps({"symptoms": [], "emergency_suspected": False}))

    assert p.extract_symptoms("text").latency_s == 1.5


def test_prompt_lists_only_candidates_when_k_is_set():
    p, client = provider(json.dumps({"symptoms": [], "emergency_suspected": False}))
    p.candidate_k = 1

    p.extract_symptoms("기침이 나요")

    instruction = client.models.calls[0]["config"].system_instruction
    listed = {line.split(":")[0] for line in instruction.splitlines() if ":" in line}
    assert "cough" in listed and "high_fever" not in listed


def fallback_provider(*replies):
    client = SimpleNamespace(models=FakeModels(replies))
    p = GeminiProvider(
        client=client,
        model="primary",
        fallback_model="backup",
        vocab=VOCAB,
        max_retries=0,
        retry_sleep=0,
    )
    return p, client


def test_falls_back_to_the_second_model_on_quota_or_server_errors():
    limited = errors.ClientError(
        429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
    )
    p, client = fallback_provider(
        limited, json.dumps({"symptoms": [], "emergency_suspected": False})
    )

    result = p.extract_symptoms("text")

    assert [c["model"] for c in client.models.calls] == ["primary", "backup"]
    assert result.parsed and result.served_model == "backup"


def test_does_not_fall_back_on_client_mistakes():
    bad = errors.ClientError(
        400, {"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}}
    )
    p, client = fallback_provider(bad)

    with pytest.raises(errors.ClientError):
        p.extract_symptoms("text")
    assert [c["model"] for c in client.models.calls] == ["primary"]


def test_raises_when_both_models_fail():
    down = errors.ServerError(
        503, {"error": {"code": 503, "message": "x", "status": "UNAVAILABLE"}}
    )
    p, client = fallback_provider(down, down)

    with pytest.raises(errors.ServerError):
        p.extract_symptoms("text")
    assert [c["model"] for c in client.models.calls] == ["primary", "backup"]
