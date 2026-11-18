"""Demo sentence stability (2026-11-18): run each scripted conversation N times against a running
stack (real Gemini) and check that the result screen is the same every time.

Each candidate has a fixed sentence and a fixed reply typed for every follow-up question, so the
whole conversation can be replayed. All sentences are made up for the demo (no user data).

A candidate is stable when, in every run:
  1. the first disease is the same and labelled "high",
  2. the recommended department is the same (and `want_department`),
  3. every Top-3 disease is in `plausible` (no unrelated disease such as migraine for a knee),
  and, for the normal demo, no emergency, no rare-disease note and no order adjustment.

Usage (stdlib only; free tier 15 RPM / 500 RPD, so runs are paced):
    python infra/scripts/demo_stability.py --base http://localhost:8000 --runs 5 --pause 20 \
        --out docs/perf/demo-stability.json
"""

import argparse
import json
import time
import urllib.error
import urllib.request

# kind: "normal" or "emergency". plausible: Top-3 diseases that make sense for the sentence.
CANDIDATES = [
    {
        "id": "acne",
        "kind": "normal",
        "text": "얼굴에 여드름이 많이 나고 고름이 잡혀요",
        "reply": "몇 주 전부터 그랬고 다른 증상은 없어요",
        "want_department": "14",
        "plausible": {
            "acne",
            "impetigo",
            "fungal_infection",
            "psoriasis",
            "allergy",
            "chicken_pox",
        },
    },
    {
        "id": "athletes-foot",
        "kind": "normal",
        "text": "발가락 사이가 너무 가렵고 피부가 하얗게 일어나요",
        "reply": "일주일 전부터 그랬고 다른 증상은 없어요",
        "want_department": "14",
        "plausible": {"fungal_infection", "psoriasis", "impetigo", "allergy", "drug_reaction"},
    },
    {
        "id": "reflux",
        "kind": "normal",
        "text": "밥 먹고 나면 속이 쓰리고 신물이 목까지 올라와요",
        "reply": "몇 주 전부터 그랬고 다른 증상은 없어요",
        "want_department": "01",
        "plausible": {"gerd", "peptic_ulcer", "gastroenteritis", "chronic_cholestasis"},
    },
    {
        "id": "neck",
        "kind": "normal",
        "text": "목 뒤가 뻐근하고 어깨까지 결리고 고개를 돌리기 힘들어요",
        "reply": "몇 주 전부터 그랬고 다른 증상은 없어요",
        "want_department": "05",
        "plausible": {"cervical_spondylosis", "osteoarthritis", "arthritis", "migraine"},
    },
    {
        "id": "cold",
        "kind": "normal",
        "text": "콧물이 계속 나고 재채기가 나고 목이 칼칼해요",
        "reply": "이틀 전부터 그랬고 열은 없어요",
        "want_department": "01",
        "plausible": {"common_cold", "allergy", "bronchial_asthma", "pneumonia"},
    },
    {
        "id": "vertigo",
        "kind": "normal",
        "text": "누웠다 일어나거나 고개를 돌리면 빙글빙글 어지러워요",
        "reply": "사흘 전부터 그랬고 다른 증상은 없어요",
        "want_department": "13",
        "plausible": {"bppv", "migraine", "hypertension", "hypoglycemia"},
    },
    {
        "id": "knee",
        "kind": "normal",
        "text": "무릎이 붓고 걸을 때 아파요",
        "reply": "몇 주 전부터 그랬고 다른 증상은 없어요",
        "want_department": "05",
        "plausible": {"osteoarthritis", "arthritis", "varicose_veins", "cervical_spondylosis"},
    },
    {
        "id": "chest",
        "kind": "emergency",
        "text": "갑자기 가슴이 아프고 식은땀이 나요",
        "reply": "방금 전부터 그래요",
        "want_department": "24",
        "plausible": {"heart_attack", "gerd", "pneumonia", "hypertension", "bronchial_asthma"},
    },
]
MAX_TURNS = 3
CALLS_PER_CONVERSATION = 4  # extract + questions, then extract + explain (upper bound per turn: +2)


def call(base, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def run_once(base, cand):
    status, session = call(base, "POST", "/api/triage/sessions", {})
    if status != 201:
        return {"ok": False, "error": f"create_{status}"}
    sid = session["session_id"]
    start = time.perf_counter()
    text, turns = cand["text"], 0
    for turns in range(1, MAX_TURNS + 2):
        status, msg = call(base, "POST", f"/api/triage/sessions/{sid}/messages", {"text": text})
        if status != 200:
            return {"ok": False, "error": msg.get("code", f"http_{status}"), "turns": turns}
        if msg["status"] == "result_ready":
            break
        text = cand["reply"]
    else:
        return {"ok": False, "error": "no_result", "turns": turns}
    status, r = call(base, "GET", f"/api/triage/sessions/{sid}/result")
    if status != 200:
        return {"ok": False, "error": f"result_{status}"}
    preds = r["predictions"]
    return {
        "ok": True,
        "total_ms": round((time.perf_counter() - start) * 1000),
        "turns": turns,
        "emergency": r["emergency"],
        "top1": preds[0]["disease_id"],
        "top1_likelihood": preds[0].get("likelihood"),
        "top3": [f"{p['disease_id']}:{p.get('likelihood')}" for p in preds],
        "department": r["recommended_departments"][0]["code"],
        "rare_note": any("note" in p for p in preds),
        "order_adjusted": bool(r.get("order_adjusted")),
    }


def judge(cand, runs):
    ok = [r for r in runs if r["ok"]]
    reasons = []
    if len(ok) < len(runs):
        reasons.append(f"failed runs {len(runs) - len(ok)}")
    if len({r["top1"] for r in ok}) > 1:
        reasons.append("top1 differs")
    if any(r["top1_likelihood"] != "high" for r in ok):
        reasons.append("top1 not high")
    if any(r["department"] != cand["want_department"] for r in ok):
        reasons.append("department differs")
    odd = sorted({t.split(":")[0] for r in ok for t in r["top3"]} - cand["plausible"])
    if odd:
        reasons.append("unrelated in top3: " + ",".join(odd))
    want_emergency = cand["kind"] == "emergency"
    if any(r["emergency"] != want_emergency for r in ok):
        reasons.append("emergency flag differs")
    if cand["kind"] == "normal" and any(r["rare_note"] or r["order_adjusted"] for r in ok):
        reasons.append("rare note / order adjusted")
    return {"stable": not reasons, "reasons": reasons}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--pause", type=float, default=20.0)
    ap.add_argument("--only", nargs="*", help="candidate ids")
    ap.add_argument("--out")
    args = ap.parse_args()

    cands = [c for c in CANDIDATES if not args.only or c["id"] in args.only]
    n = len(cands) * args.runs
    print(
        f"plan: {len(cands)} candidates x {args.runs} runs = {n} conversations, "
        f"about {n * CALLS_PER_CONVERSATION} Gemini calls (up to {n * (2 + 2 * MAX_TURNS)}), "
        f"pause {args.pause}s; free tier 15 RPM / 500 RPD",
        flush=True,
    )
    report = {"runs_per_candidate": args.runs, "candidates": []}
    for cand in cands:
        runs = []
        for i in range(args.runs):
            r = run_once(args.base, cand)
            runs.append(r)
            print(cand["id"], i + 1, json.dumps(r, ensure_ascii=False), flush=True)
            time.sleep(args.pause)
        entry = {k: (sorted(v) if isinstance(v, set) else v) for k, v in cand.items()}
        entry |= {"runs": runs, **judge(cand, runs)}
        report["candidates"].append(entry)
        print(cand["id"], "->", entry["stable"], entry["reasons"], flush=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
