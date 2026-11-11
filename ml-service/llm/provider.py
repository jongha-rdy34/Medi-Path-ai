"""LLMProvider interface and provider-independent safety filters (T13, SPEC 3.1).

Code depends only on LLMProvider (extract_symptoms, next_questions, explain),
so Gemini and a local LoRA model (T52) are swapped by configuration.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from triage.data import RISK_FACTORS

SYMPTOMS_CSV = Path(__file__).resolve().parents[2] / "data" / "mappings" / "symptoms.csv"
SEVERITIES = ("mild", "moderate", "severe")

# Questions about risk factors (on hold, SPEC section 6) or identity are never asked.
BLOCKED_QUESTION_TERMS = (
    "성관계", "성 접촉", "성접촉", "배우자", "주사", "문신", "수혈",
    "가족력", "가족 중", "가족중", "부모님", "이름", "주소", "연락처", "전화번호", "주민",
)  # fmt: skip
FALLBACK_EXPLANATION = (
    "입력하신 증상을 바탕으로 가능성이 있는 질환과 진료과를 안내해 드렸습니다. "
    "증상이 심해지거나 오래가면 의료진에게 진료를 받으세요."
)


@dataclass(frozen=True)
class Symptom:
    symptom_id: str
    severity: str | None = None
    duration_days: int | None = None


@dataclass
class Extraction:
    symptoms: list[Symptom]
    emergency_suspected: bool = False
    emergency_reason: str | None = None
    parsed: bool = True
    latency_s: float = 0.0
    prompt_tokens: int = 0
    output_tokens: int = 0
    raw: dict = field(default_factory=dict)


class LLMProvider(Protocol):
    def extract_symptoms(self, text: str) -> Extraction: ...

    def next_questions(self, symptom_ids: list[str]) -> list[dict]: ...

    def explain(self, disease_names: list[str], symptom_ids: list[str]) -> str: ...


def load_symptom_dictionary(path: Path = SYMPTOMS_CSV) -> dict[str, str]:
    """symptom_id -> '한국어명 (동의어, ...)' for prompts, without risk factors."""
    with path.open(encoding="utf-8", newline="") as f:
        out = {}
        for r in csv.DictReader(f):
            if r["symptom_id"] in RISK_FACTORS:
                continue
            synonyms = [s for s in r["synonyms_ko"].split("|") if s]
            out[r["symptom_id"]] = r["name_ko"] + (f" ({', '.join(synonyms)})" if synonyms else "")
        return out


def sanitize_symptoms(items: list, allowed: set[str]) -> list[Symptom]:
    """Keep known, non-risk-factor ids once each; drop invalid severity/duration."""
    seen, out = set(), []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        sid = item.get("symptom_id")
        if sid not in allowed or sid in RISK_FACTORS or sid in seen:
            continue
        seen.add(sid)
        severity = item.get("severity") if item.get("severity") in SEVERITIES else None
        days = item.get("duration_days")
        days = days if isinstance(days, int) and not isinstance(days, bool) and days >= 0 else None
        out.append(Symptom(sid, severity, days))
    return out


def filter_questions(questions: list, limit: int = 3) -> list[dict]:
    kept = []
    for q in questions if isinstance(questions, list) else []:
        text = q.get("text", "") if isinstance(q, dict) else ""
        if text.strip() and not any(term in text for term in BLOCKED_QUESTION_TERMS):
            kept.append(q)
    return kept[:limit]


def sanitize_explanation(text: str) -> str:
    """The service gives guidance, not a diagnosis (SPEC section 6)."""
    text = (text or "").strip()
    return text.replace("진단", "판단") if text else FALLBACK_EXPLANATION
