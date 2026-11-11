"""Session orchestration: extract -> merge -> red flags -> questions or result.

Raw text is passed to the LLM client and dropped; only structured symptoms
are kept (SPEC section 6). Emergency = rules OR LLM.
"""

from __future__ import annotations

from django.utils import timezone

from triage import clients, mappings
from triage.models import TriageSession

DISCLAIMER = (
    "이 결과는 의학적 진단이 아니며 참고용 안내입니다. 정확한 진단과 치료는 의료진에게 받으세요."
)
EMERGENCY_MESSAGE = "지금 바로 119에 전화하거나 가까운 응급실로 가세요."
MAX_QUESTION_TURNS = 1  # ask follow-up questions at most once
MIN_SYMPTOMS_FOR_RESULT = 3


def emergency_notice(session: TriageSession) -> dict | None:
    if not session.emergency:
        return None
    return {
        "reasons": session.emergency_reasons,
        "message": EMERGENCY_MESSAGE,
        "call_number": "119",
    }


def structured(session: TriageSession) -> dict:
    return {"symptoms": session.symptoms}


def handle_message(session: TriageSession, text: str) -> dict:
    extracted = clients.llm_client.extract_symptoms(text)
    known = {s["symptom_id"] for s in session.symptoms}
    session.symptoms = session.symptoms + [
        s for s in extracted.symptoms if s["symptom_id"] not in known
    ]
    session.turns += 1

    reasons = clients.safety_client.check(session.symptoms)
    if extracted.emergency_suspected and extracted.emergency_reason:
        reasons.append(extracted.emergency_reason)
    if reasons:
        session.emergency, session.emergency_reasons = True, reasons

    ready = (
        session.emergency
        or session.turns > MAX_QUESTION_TURNS
        or len(session.symptoms) >= MIN_SYMPTOMS_FOR_RESULT
    )
    common = {
        "session_id": str(session.id),
        "structured_symptoms": structured(session),
        "emergency": session.emergency,
        "emergency_notice": emergency_notice(session),
    }
    if ready and session.symptoms:
        session.result = build_result(session)
        session.status = TriageSession.Status.RESULT_READY
        session.save()
        return {
            "status": "result_ready",
            **common,
            "result_url": f"/api/triage/sessions/{session.id}/result",
        }

    session.save()
    ids = [s["symptom_id"] for s in session.symptoms]
    return {
        "status": "needs_more_info",
        **common,
        "questions": clients.llm_client.next_questions(ids),
    }


def build_result(session: TriageSession) -> dict:
    ids = [s["symptom_id"] for s in session.symptoms]
    version, ranked = clients.ml_client.predict(ids, top_k=3)
    known = mappings.diseases()
    predictions = [
        {"disease_id": d, "disease_name_ko": known[d]["disease_name_ko"], "probability": p}
        for d, p in ranked
        if d in known
    ]
    if session.emergency:
        departments = [
            {
                "code": "24",
                "name_ko": mappings.departments()["24"],
                "reason": session.emergency_reasons[0],
            }
        ]
    else:
        top = known[predictions[0]["disease_id"]]
        code = top["department_code"]
        departments = [
            {"code": code, "name_ko": mappings.departments()[code], "reason": top["reason_ko"]}
        ]
    explanation = clients.llm_client.explain([p["disease_name_ko"] for p in predictions], ids)
    return {
        "session_id": str(session.id),
        "emergency": session.emergency,
        "emergency_notice": emergency_notice(session),
        "predictions": predictions,
        "recommended_departments": departments,
        "explanation": explanation,
        "structured_symptoms": structured(session),
        "disclaimer": DISCLAIMER,
        "model_version": version,
        "created_at": timezone.now().isoformat(),
    }
