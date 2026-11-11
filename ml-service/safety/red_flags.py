"""Rule-based red-flag check (T15). Rules: safety/red_flags.yaml.

The backend ORs this with the LLM's emergency judgement (SPEC section 6),
so this module never depends on the LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import yaml

RULES_PATH = Path(__file__).with_name("red_flags.yaml")
MESSAGE_KO = "지금 바로 119에 전화하거나 가까운 응급실로 가세요."


@dataclass(frozen=True)
class Observation:
    symptom_id: str
    severity: str | None = None


@dataclass(frozen=True)
class Rule:
    id: str
    reason_ko: str
    source: str
    any_of: frozenset[str] = frozenset()
    all_of: frozenset[str] = frozenset()
    with_any: frozenset[str] = frozenset()
    severe_any: frozenset[str] = frozenset()

    def symptom_ids(self) -> set[str]:
        return set(self.any_of | self.all_of | self.with_any | self.severe_any)

    def matches(self, present: set[str], severe: set[str]) -> bool:
        return (
            (not self.any_of or bool(self.any_of & present))
            and self.all_of <= present
            and (not self.with_any or bool(self.with_any & present))
            and (not self.severe_any or bool(self.severe_any & severe))
        )


@dataclass(frozen=True)
class EmergencyResult:
    is_emergency: bool
    reasons: list[str] = field(default_factory=list)
    rule_ids: list[str] = field(default_factory=list)
    message: str = MESSAGE_KO
    call_number: str = "119"


@cache
def load_rules(path: Path = RULES_PATH) -> tuple[Rule, ...]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules = []
    for r in doc["rules"]:
        conditions = {
            k: frozenset(r.get(k, [])) for k in ("any_of", "all_of", "with_any", "severe_any")
        }
        if not any(conditions.values()):
            raise ValueError(f"rule {r['id']} has no condition")
        rules.append(Rule(id=r["id"], reason_ko=r["reason_ko"], source=r["source"], **conditions))
    return tuple(rules)


def check(observations: list[Observation]) -> EmergencyResult:
    present = {o.symptom_id for o in observations}
    severe = {o.symptom_id for o in observations if o.severity == "severe"}
    matched = [r for r in load_rules() if r.matches(present, severe)]
    return EmergencyResult(
        is_emergency=bool(matched),
        reasons=[r.reason_ko for r in matched],
        rule_ids=[r.id for r in matched],
    )
