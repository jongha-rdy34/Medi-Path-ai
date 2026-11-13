"""Measure time-to-result of the triage flow against a running stack (T30, SPEC p95 < 10 s).

Each run: create a session, send one symptom sentence, answer follow-up questions with a fixed
reply until result_ready, then GET the result. The clock covers the first message to the result
response, i.e. what the user waits for (session creation happens on page load).

The sentences below are synthetic test inputs, not user data. The JSON report only holds
sentence indexes, statuses, timings and IDs, never the text.

Usage (stdlib only):
    python infra/scripts/measure_triage_latency.py --base http://localhost:8000 --runs 20 \
        --pause 12 --out ml-service/llm/eval/results/latency-t30.json
"""

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request

SENTENCES = [
    "어제부터 열이 나고 기침과 누런 가래가 나와요",
    "갑자기 가슴이 아프고 식은땀이 나요",
    "사흘째 배가 아프고 설사를 해요",
    "머리가 지끈거리고 속이 메스꺼워요",
    "목이 따갑고 콧물이 계속 나요",
    "소변 볼 때 따갑고 자주 마려워요",
    "피부에 붉은 발진이 생기고 가려워요",
    "무릎이 붓고 걸을 때 아파요",
    "밥 먹고 나면 속이 쓰리고 신물이 올라와요",
    "어지럽고 기운이 없어요",
]
FOLLOW_UP_REPLY = "이틀 전부터 그랬고 꽤 심해요"
MAX_TURNS = 4


def call(base: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def run_once(base: str, sentence: str) -> dict:
    status, session = call(base, "POST", "/api/triage/sessions", {})
    if status != 201:
        return {"ok": False, "error": f"create_{status}"}
    sid = session["session_id"]
    start = time.perf_counter()
    turn_ms, text = [], sentence
    for _ in range(MAX_TURNS):
        t0 = time.perf_counter()
        status, msg = call(base, "POST", f"/api/triage/sessions/{sid}/messages", {"text": text})
        turn_ms.append(round((time.perf_counter() - t0) * 1000))
        if status != 200:
            return {"ok": False, "error": msg.get("code", f"http_{status}"), "turn_ms": turn_ms}
        if msg["status"] == "result_ready":
            break
        text = FOLLOW_UP_REPLY
    else:
        return {"ok": False, "error": "no_result", "turn_ms": turn_ms}
    status, result = call(base, "GET", f"/api/triage/sessions/{sid}/result")
    total_ms = round((time.perf_counter() - start) * 1000)
    if status != 200:
        return {"ok": False, "error": f"result_{status}", "turn_ms": turn_ms}
    return {
        "ok": True,
        "total_ms": total_ms,
        "turn_ms": turn_ms,
        "turns": len(turn_ms),
        "emergency": result.get("emergency"),
        "top3": [p["disease_id"] for p in result.get("predictions", [])],
        "departments": [d.get("code") for d in result.get("recommended_departments", [])],
    }


def percentile(values: list[int], q: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q * len(ordered) + 0.5) - 1))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--pause", type=float, default=12.0, help="seconds between runs (15 RPM)")
    ap.add_argument("--out")
    args = ap.parse_args()

    runs = []
    for i in range(args.runs):
        idx = i % len(SENTENCES)
        r = {"run": i + 1, "sentence_index": idx, **run_once(args.base, SENTENCES[idx])}
        runs.append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        if i + 1 < args.runs:
            time.sleep(args.pause)

    totals = [r["total_ms"] for r in runs if r["ok"]]
    summary = {
        "runs": len(runs),
        "ok": len(totals),
        "failures": [r["error"] for r in runs if not r["ok"]],
        "p50_ms": percentile(totals, 0.5) if totals else None,
        "p95_ms": percentile(totals, 0.95) if totals else None,
        "max_ms": max(totals) if totals else None,
        "mean_ms": round(statistics.mean(totals)) if totals else None,
    }
    print(json.dumps(summary, ensure_ascii=False))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "runs": runs}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
