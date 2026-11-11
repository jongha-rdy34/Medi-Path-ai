"""LLM symptom-extraction evaluation (T13).

Usage (from ml-service/):
    python -m llm.eval --provider gemini --model gemini-3.5-flash-lite
    python -m llm.eval --provider gemini --limit 5          # quick check

Writes llm/eval/results/<model>.json (per-case output + summary). Cases are
fictional sentences (llm/eval/cases.jsonl); no personal data is sent.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from llm.provider import Extraction
from triage.data import RISK_FACTORS

CASES_PATH = Path(__file__).with_name("cases.jsonl")
RESULTS_DIR = Path(__file__).with_name("results")


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def score(expected: list[str], extraction: Extraction) -> dict:
    got = {s.symptom_id for s in extraction.symptoms}
    want = set(expected)
    return {"tp": len(got & want), "fp": len(got - want), "fn": len(want - got)}


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def summarize(rows: list[dict], price_in: float | None, price_out: float | None) -> dict:
    totals = {"tp": 0, "fp": 0, "fn": 0}
    for r in rows:
        for k, v in score(r["case"]["expected_symptoms"], r["extraction"]).items():
            totals[k] += v
    precision = totals["tp"] / max(1, totals["tp"] + totals["fp"])
    recall = totals["tp"] / max(1, totals["tp"] + totals["fn"])
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    ex = [r["extraction"] for r in rows]
    avg_in = sum(e.prompt_tokens for e in ex) / len(ex)
    avg_out = sum(e.output_tokens for e in ex) / len(ex)
    cost = None
    if price_in is not None and price_out is not None:
        cost = round(1000 * (avg_in * price_in + avg_out * price_out) / 1_000_000, 4)
    raw_ids = [
        s.get("symptom_id")
        for e in ex
        for s in (e.raw.get("symptoms") or [])
        if isinstance(s, dict)
    ]
    return {
        "cases": len(rows),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "json_parse_rate": round(sum(e.parsed for e in ex) / len(ex), 4),
        "latency_avg_s": round(sum(e.latency_s for e in ex) / len(ex), 3),
        "latency_p95_s": round(_p95([e.latency_s for e in ex]), 3),
        "avg_prompt_tokens": round(avg_in, 1),
        "avg_output_tokens": round(avg_out, 1),
        "cost_per_1k_calls_usd": cost,
        "risk_factor_ids_in_raw_output": sum(i in RISK_FACTORS for i in raw_ids),
        "emergency_suspected_cases": sum(e.emergency_suspected for e in ex),
    }


def make_provider(name: str, model: str | None):
    if name == "gemini":
        from llm.gemini import GeminiProvider

        return GeminiProvider(model=model)
    raise SystemExit(f"unknown provider: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate LLM symptom extraction")
    parser.add_argument("--provider", default="gemini")
    parser.add_argument(
        "--model", default=None, help="defaults to GEMINI_MODEL or the provider default"
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--sleep", type=float, default=6.0, help="seconds between calls (free-tier RPM)"
    )
    parser.add_argument(
        "--price-in", type=float, default=None, help="USD per 1M input tokens (paid tier)"
    )
    parser.add_argument(
        "--price-out", type=float, default=None, help="USD per 1M output tokens (paid tier)"
    )
    args = parser.parse_args()

    provider = make_provider(args.provider, args.model)
    cases = load_cases()[: args.limit]
    rows = []
    for i, case in enumerate(cases, 1):
        extraction = provider.extract_symptoms(case["text"])
        rows.append({"case": case, "extraction": extraction})
        print(
            f"[{i}/{len(cases)}] {case['id']} {score(case['expected_symptoms'], extraction)}",
            flush=True,
        )
        if i < len(cases):
            time.sleep(args.sleep)

    summary = summarize(rows, args.price_in, args.price_out)
    model = getattr(provider, "model", args.provider)
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{model}.json"
    out.write_text(
        json.dumps(
            {
                "provider": args.provider,
                "model": model,
                "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "summary": summary,
                "cases": [
                    {
                        "id": r["case"]["id"],
                        "expected": r["case"]["expected_symptoms"],
                        "disease_id": r["case"]["disease_id"],
                        "extraction": {
                            k: v for k, v in asdict(r["extraction"]).items() if k != "raw"
                        },
                    }
                    for r in rows
                ],
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    print(json.dumps(summary, indent=2))
    print(f"results: {out}")
    return 0
