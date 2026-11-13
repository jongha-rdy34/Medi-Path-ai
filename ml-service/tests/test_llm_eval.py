from llm.eval.run import CASES_PATH, load_cases, score, summarize
from llm.provider import Extraction, Symptom


def ext(ids, ms=1.0, parsed=True):
    return Extraction(
        symptoms=[Symptom(i) for i in ids],
        parsed=parsed,
        latency_s=ms,
        prompt_tokens=1000,
        output_tokens=50,
    )


def test_cases_file_is_valid():
    cases = load_cases(CASES_PATH)

    assert 50 <= len(cases) <= 100
    assert len({c["disease_id"] for c in cases}) == 41


def test_score_counts_true_and_false_positives():
    s = score(["a", "b"], ext(["a", "c"]))

    assert (s["tp"], s["fp"], s["fn"]) == (1, 1, 1)


def test_summary_metrics():
    rows = [
        {"case": {"expected_symptoms": ["a", "b"]}, "extraction": ext(["a", "b"], 1.0)},
        {"case": {"expected_symptoms": ["a"]}, "extraction": ext(["a", "x"], 3.0)},
        {"case": {"expected_symptoms": ["a"]}, "extraction": ext([], 2.0, parsed=False)},
    ]

    m = summarize(rows, price_in=0.1, price_out=0.4)

    assert m["cases"] == 3 and m["json_parse_rate"] == round(2 / 3, 4)
    assert (m["precision"], m["recall"]) == (0.75, 0.75) and m["f1"] == 0.75
    assert m["latency_avg_s"] == 2.0 and m["latency_p95_s"] == 3.0
    # 1000 in + 50 out tokens per call at $0.1 / $0.4 per 1M tokens -> per 1000 calls
    assert m["cost_per_1k_calls_usd"] == round(1000 * (1000 * 0.1 + 50 * 0.4) / 1_000_000, 4)


def test_summary_without_prices_reports_unknown_cost():
    m = summarize([{"case": {"expected_symptoms": ["a"]}, "extraction": ext(["a"])}], None, None)

    assert m["cost_per_1k_calls_usd"] is None


class CountingProvider:
    model = "fake-model"

    def __init__(self):
        self.calls = 0

    def extract_symptoms(self, text):
        self.calls += 1
        return ext(["a"])


def test_cache_avoids_repeat_calls_and_reports_planned_calls(tmp_path):
    from llm.eval.run import CachedExtractor

    provider = CountingProvider()
    cached = CachedExtractor(provider, tmp_path)
    cases = [{"text": "열이 나요"}, {"text": "기침해요"}]

    assert cached.planned_calls(cases) == 2
    first, called = cached.extract("열이 나요")
    assert called
    assert cached.planned_calls(cases) == 1

    again, called_again = CachedExtractor(provider, tmp_path).extract("열이 나요")

    assert not called_again

    assert provider.calls == 1
    assert [s.symptom_id for s in again.symptoms] == [s.symptom_id for s in first.symptoms]


def test_cache_and_results_are_separated_by_prompt_variant(tmp_path):
    from llm.eval.run import CachedExtractor, run_tag

    full, slim = CountingProvider(), CountingProvider()
    slim.candidate_k = 30

    assert run_tag(full) == "fake-model" and run_tag(slim) == "fake-model-k30"
    CachedExtractor(full, tmp_path).extract("열이 나요")
    _, called = CachedExtractor(slim, tmp_path).extract("열이 나요")
    assert called and slim.calls == 1
