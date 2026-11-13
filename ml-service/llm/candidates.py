"""Pick the symptom-dictionary lines relevant to one input (T30 prompt slimming).

Sending all 128 dictionary lines made the extraction prompt ~2,684 input
tokens. We send only symptoms whose Korean name or synonym overlaps the input
(character bigrams), plus a fixed set of emergency symptoms so red flags are
never dropped from the prompt.
"""

from __future__ import annotations

import re

from triage.data import RISK_FACTORS

# Kept in every prompt: missing one of these would hide an emergency (T15 rules).
ALWAYS_INCLUDE = (
    "chest_pain",
    "breathlessness",
    "altered_sensorium",
    "coma",
    "weakness_of_one_body_side",
    "slurred_speech",
    "blood_in_sputum",
    "stomach_bleeding",
)


def _compact(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text)


def _bigrams(text: str) -> set[str]:
    t = _compact(text)
    return {t[i : i + 2] for i in range(len(t) - 1)} if len(t) > 1 else {t} if t else set()


def _terms(entry: str) -> list[str]:
    """'고열 (열이 높음, 열이 펄펄 남)' -> ['고열', '열이 높음', '열이 펄펄 남']; '·' splits too."""
    name, _, rest = entry.partition(" (")
    terms = [name] + [s for s in rest.rstrip(")").split(", ") if s]
    return [part for t in terms for part in t.split("·") if part.strip()]


def score(text: str, entry: str) -> float:
    """Bigram overlap with the best term; a term whose stem (last syllable dropped,
    e.g. 토함 -> 토, 속쓰림 -> 속쓰리) appears in the text counts as a weak match,
    so verb endings (토할, 떨리고) still find the symptom."""
    compact = _compact(text)
    grams = _bigrams(text)
    best = 0.0
    for term in _terms(entry):
        tg = _bigrams(term)
        if tg:
            best = max(best, len(tg & grams) / len(tg))
        stem = _compact(term)[:-1]
        if stem and stem in compact:
            best = max(best, 0.5)
    return best


def select_candidates(text: str, vocab: dict[str, str], k: int = 30) -> list[str]:
    """Top-k matching symptom ids (score > 0) plus ALWAYS_INCLUDE, risk factors removed."""
    scored = sorted(
        ((score(text, entry), sid) for sid, entry in vocab.items() if sid not in RISK_FACTORS),
        key=lambda x: (-x[0], x[1]),
    )
    picked = [sid for s, sid in scored if s > 0][:k]
    picked += [sid for sid in ALWAYS_INCLUDE if sid in vocab and sid not in picked]
    return picked
