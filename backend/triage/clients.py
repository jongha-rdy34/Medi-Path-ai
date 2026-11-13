"""Clients for the LLM, ml-service and red-flag rules.

W2 (T22) uses deterministic stubs so the backend runs without the LLM or
ml-service; T30 swaps in the real clients behind the same methods.
Hospital search is not here: it belongs to backend/hospitals/ (@ley-21, T21).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass
class Extracted:
    symptoms: list[dict]
    emergency_suspected: bool = False
    emergency_reason: str | None = None


class StubLLMClient:
    """Keyword matcher standing in for LLMProvider.extract_symptoms / next_questions / explain."""

    KEYWORDS: ClassVar[dict[str, str]] = {
        "열": "high_fever",
        "기침": "cough",
        "가래": "phlegm",
        "가슴": "chest_pain",
        "숨": "breathlessness",
        "설사": "diarrhoea",
        "토": "vomiting",
        "배": "abdominal_pain",
        "머리": "headache",
        "콧물": "runny_nose",
    }

    def extract_symptoms(self, text: str) -> Extracted:
        found = [sid for kw, sid in self.KEYWORDS.items() if kw in text]
        return Extracted(symptoms=[{"symptom_id": s} for s in dict.fromkeys(found)])

    def next_questions(self, symptom_ids: list[str]) -> list[dict]:
        return [
            {
                "question_id": "q1",
                "text": "증상이 언제부터 시작됐나요?",
                "choices": ["오늘", "1~2일 전", "3일 이상"],
            },
            {"question_id": "q2", "text": "함께 있는 다른 증상이 있나요?"},
        ]

    def explain(self, disease_names: list[str], symptom_ids: list[str]) -> str:
        return (
            f"입력하신 증상은 {', '.join(disease_names[:2])} 등에서 나타날 수 있습니다. "
            "증상이 심해지거나 오래가면 진료를 받으세요."
        )


class StubMLClient:
    """Fixed rankings standing in for ml-service POST /predict."""

    VERSION = "stub-0"

    def predict(
        self, symptom_ids: list[str], top_k: int = 3
    ) -> tuple[str, list[tuple[str, float]]]:
        s = set(symptom_ids)
        if "chest_pain" in s:
            ranked = [("heart_attack", 0.56), ("pneumonia", 0.14), ("gerd", 0.08)]
        elif s & {"cough", "phlegm"}:
            ranked = [("pneumonia", 0.48), ("bronchial_asthma", 0.21), ("common_cold", 0.12)]
        else:
            ranked = [("gastroenteritis", 0.52), ("typhoid", 0.23), ("hepatitis_a", 0.09)]
        return self.VERSION, ranked[:top_k]


class StubSafetyClient:
    """Subset of ml-service/safety/red_flags.yaml (T15) until T30 wires the real rules."""

    def check(self, symptoms: list[dict]) -> list[str]:
        ids = {s["symptom_id"] for s in symptoms}
        reasons = []
        if "chest_pain" in ids:
            reasons.append("가슴 통증이 있습니다. 증상만으로는 심장 원인을 배제할 수 없습니다.")
        if "breathlessness" in ids and any(s.get("severity") == "severe" for s in symptoms):
            reasons.append("숨쉬기가 매우 힘든 상태입니다.")
        return reasons


def build():
    """(llm, ml, safety) clients per settings.TRIAGE_CLIENTS: "http" (ml-service) or "stub"."""
    from django.conf import settings

    if getattr(settings, "TRIAGE_CLIENTS", "http") == "stub":
        return StubLLMClient(), StubMLClient(), StubSafetyClient()
    from triage.http_clients import HttpLLMClient, HttpMLClient, HttpSafetyClient

    url = settings.ML_SERVICE_URL
    # LLM calls get a longer timeout: primary + fallback model with retries (ADR 0001).
    return (
        HttpLLMClient(url, timeout=30.0),
        HttpMLClient(url, timeout=5.0),
        HttpSafetyClient(url, timeout=5.0),
    )


llm_client, ml_client, safety_client = build()
