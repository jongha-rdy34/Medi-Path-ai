"""T22: session / message / result endpoints against contracts/openapi.yaml (stub clients).

/api/hospitals is owned by @ley-21 (backend/hospitals/) and is not tested here.
"""

import json
import logging
import uuid

import pytest

from tests.contract import validate
from triage.models import TriageSession

pytestmark = pytest.mark.django_db
SESSIONS = "/api/triage/sessions"


def create(client, body=None):
    res = client.post(
        SESSIONS, data=json.dumps(body) if body else None, content_type="application/json"
    )
    return res


def send(client, sid, text):
    return client.post(
        f"{SESSIONS}/{sid}/messages",
        data=json.dumps({"text": text}),
        content_type="application/json",
    )


def test_create_session(client):
    res = create(client)

    assert res.status_code == 201
    validate(res.json(), "Session")
    assert res.json()["status"] == "collecting"


def test_create_session_with_region_and_invalid_region(client):
    assert create(client, {"region_code": "11680"}).status_code == 201

    bad = create(client, {"region_code": "123"})

    assert bad.status_code == 422
    validate(bad.json(), "Error")
    assert bad.json()["code"] == "validation_error"


def test_vague_message_asks_follow_up_questions(client):
    sid = create(client).json()["session_id"]

    res = send(client, sid, "어제부터 열이 나요")

    assert res.status_code == 200
    body = res.json()
    validate(body, "MessageResponse")
    assert body["status"] == "needs_more_info" and 1 <= len(body["questions"]) <= 3
    assert {s["symptom_id"] for s in body["structured_symptoms"]["symptoms"]} == {"high_fever"}


def test_answer_leads_to_result(client):
    sid = create(client).json()["session_id"]
    send(client, sid, "열이 나요")

    res = send(client, sid, "기침도 나고 가래가 있어요")

    assert res.status_code == 200 and res.json()["status"] == "result_ready"
    validate(res.json(), "MessageResponse")
    result = client.get(f"{SESSIONS}/{sid}/result")
    assert result.status_code == 200
    data = result.json()
    validate(data, "TriageResult")
    assert data["emergency"] is False and data["emergency_notice"] is None
    assert 1 <= len(data["predictions"]) <= 3 and data["recommended_departments"]
    assert "진단이 아니며" in data["disclaimer"]
    assert {s["symptom_id"] for s in data["structured_symptoms"]["symptoms"]} == {
        "high_fever",
        "cough",
        "phlegm",
    }


def test_emergency_is_reported_immediately(client):
    sid = create(client).json()["session_id"]

    res = send(client, sid, "가슴이 아프고 숨이 차요")

    body = res.json()
    validate(body, "MessageResponse")
    assert body["status"] == "result_ready" and body["emergency"] is True
    assert body["emergency_notice"]["call_number"] == "119"
    result = client.get(f"{SESSIONS}/{sid}/result").json()
    validate(result, "TriageResult")
    assert result["emergency"] is True


def test_result_before_ready_is_409(client):
    sid = create(client).json()["session_id"]

    res = client.get(f"{SESSIONS}/{sid}/result")

    assert res.status_code == 409 and res.json()["code"] == "result_not_ready"
    validate(res.json(), "Error")


def test_message_after_result_is_409(client):
    sid = create(client).json()["session_id"]
    send(client, sid, "가슴이 아파요")

    res = send(client, sid, "또 아파요")

    assert res.status_code == 409 and res.json()["code"] == "session_completed"


@pytest.mark.parametrize("sid", [str(uuid.uuid4()), "not-a-uuid"])
def test_unknown_session_is_404(client, sid):
    for res in (send(client, sid, "열이 나요"), client.get(f"{SESSIONS}/{sid}/result")):
        assert res.status_code == 404
        validate(res.json(), "Error")
        assert res.json()["code"] == "session_not_found"


@pytest.mark.parametrize("text", ["", "가" * 501])
def test_invalid_text_is_422(client, text):
    sid = create(client).json()["session_id"]

    res = send(client, sid, text)

    assert res.status_code == 422
    validate(res.json(), "Error")


def test_raw_text_is_never_stored_or_logged(client, caplog):
    sid = create(client).json()["session_id"]
    secret_phrase = "어제 회사에서 열이 나고 기침했어요"

    with caplog.at_level(logging.DEBUG):
        send(client, sid, secret_phrase)
        send(client, sid, "가래도 있어요")

    stored = json.dumps(
        [list(TriageSession.objects.values().filter(pk=sid))], default=str, ensure_ascii=False
    )
    assert "회사" not in stored and "가래도" not in stored
    assert "회사" not in caplog.text
