"""Session orchestration: extract -> merge -> red flags -> questions or result.

Raw text is passed to the LLM client and dropped; only structured symptoms
are kept (SPEC section 6). Emergency = rules OR LLM.

Sensitive diseases (data/mappings/sensitive_diseases.csv) are removed from the
user-facing Top-3 and from the explanation prompt, and the next ranks fill in.
They still count toward the department score. Whether one was hidden is not
recorded anywhere (response, DB or logs). /predict itself is unchanged.
"""

from __future__ import annotations

import logging

from django.utils import timezone

from triage import clients, mappings
from triage.errors import ApiError
from triage.http_clients import ServiceUnavailable
from triage.models import TriageSession

log = logging.getLogger("triage")

DISCLAIMER = (
    "이 결과는 의학적 진단이 아니며 참고용 안내입니다. 정확한 진단과 치료는 의료진에게 받으세요."
)
EMERGENCY_MESSAGE = "지금 바로 119에 전화하거나 가까운 응급실로 가세요."
MAX_QUESTION_TURNS = 1  # ask follow-up questions at most once
MIN_SYMPTOMS_FOR_RESULT = 3
ML_TOP_K = 10  # enough to refill Top-3 after hiding sensitive diseases
RETRY_MESSAGE = "증상 분석이 잠시 어렵습니다. 잠시 후 다시 시도해 주세요."
FALLBACK_QUESTIONS = [
    {
        "question_id": "q1",
        "text": "증상이 언제부터 시작됐나요?",
        "choices": ["오늘", "1~2일 전", "3일 이상"],
    },
    {"question_id": "q2", "text": "함께 있는 다른 증상이 있나요?"},
]
FALLBACK_EXPLANATION = (
    "입력하신 증상을 바탕으로 가능성이 있는 질환과 권장 진료과를 안내해 드렸습니다. "
    "증상이 심해지거나 오래가면 의료진에게 진료를 받으세요."
)
# Emergency results only point to 119 or the ER (T30 follow-up C-3).
EMERGENCY_EXPLANATION = (
    "위급할 수 있는 신호가 있습니다. 지금 바로 119에 연락하거나 가까운 응급실로 가세요."
)
GENERAL_VISIT_TERMS = ("병원", "의원", "내원", "외래", "진료를 받", "진료받")


def unavailable(exc: ServiceUnavailable) -> ApiError:
    # Cause code only; never the user's text (SPEC section 6).
    log.warning("triage_unavailable code=%s", exc.code)
    return ApiError(503, exc.code, RETRY_MESSAGE)


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
    # External calls first: if they fail, the session is left exactly as it was.
    try:
        extracted = clients.llm_client.extract_symptoms(text)
        known = {s["symptom_id"] for s in session.symptoms}
        merged = session.symptoms + [s for s in extracted.symptoms if s["symptom_id"] not in known]
        reasons = clients.safety_client.check(merged)
    except ServiceUnavailable as exc:
        raise unavailable(exc) from None
    session.symptoms = merged
    session.turns += 1

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
        try:
            session.result = build_result(session)
        except ServiceUnavailable as exc:
            raise unavailable(exc) from None
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
        "questions": _questions(ids),
    }


def _questions(ids: list[str]) -> list[dict]:
    try:
        return clients.llm_client.next_questions(ids) or FALLBACK_QUESTIONS
    except ServiceUnavailable as exc:
        log.warning("questions_fallback code=%s", exc.code)
        return FALLBACK_QUESTIONS


def _explain(names: list[str], ids: list[str], emergency: bool) -> str:
    fallback = EMERGENCY_EXPLANATION if emergency else FALLBACK_EXPLANATION
    try:
        text = clients.llm_client.explain(names, ids, emergency) or fallback
    except ServiceUnavailable as exc:
        log.warning("explain_fallback code=%s", exc.code)
        return fallback
    # Defense in depth: ml-service already filters, but never show a regular-visit hint
    # on an emergency result.
    if emergency and ("119" not in text or any(t in text for t in GENERAL_VISIT_TERMS)):
        return EMERGENCY_EXPLANATION
    return text


def department_scores(ranked: list[tuple[str, float]]) -> dict[str, float]:
    """Sum of disease probabilities per primary department, hidden diseases included."""
    known = mappings.diseases()
    scores: dict[str, float] = {}
    for disease, probability in ranked:
        if disease in known:
            code = known[disease]["department_code"]
            scores[code] = scores.get(code, 0.0) + probability
    return scores


def recommend_department(ranked: list[tuple[str, float]], visible: list[str]) -> dict:
    known = mappings.diseases()
    scores = department_scores(ranked)
    code = max(scores, key=scores.get)
    name = mappings.departments()[code]
    reason = next(
        (known[d]["reason_ko"] for d in visible if known[d]["department_code"] == code),
        f"입력하신 증상에는 {name} 진료가 적합할 가능성이 높습니다.",
    )
    return {"code": code, "name_ko": name, "reason": reason}


def build_result(session: TriageSession) -> dict:
    ids = [s["symptom_id"] for s in session.symptoms]
    version, ranked = clients.ml_client.predict(ids, top_k=ML_TOP_K)
    known = mappings.diseases()
    hidden = mappings.sensitive_disease_ids()
    visible = [(d, p) for d, p in ranked if d in known and d not in hidden][:3]
    predictions = [
        {"disease_id": d, "disease_name_ko": known[d]["disease_name_ko"], "probability": p}
        for d, p in visible
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
        departments = [recommend_department(ranked, [d for d, _ in visible])]
    explanation = _explain([p["disease_name_ko"] for p in predictions], ids, session.emergency)
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
