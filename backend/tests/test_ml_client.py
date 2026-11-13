"""HTTP clients for ml-service (contracts/ml-service.openapi.yaml), against a local fake server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from triage.http_clients import HttpLLMClient, HttpMLClient, HttpSafetyClient, ServiceUnavailable

ROUTES = {
    "/predict": (
        200,
        {
            "model_version": "baseline-x",
            "predictions": [{"disease_id": "pneumonia", "probability": 0.6}],
            "unknown_symptom_ids": [],
        },
    ),
    "/llm/extract": (
        200,
        {
            "symptoms": [{"symptom_id": "cough"}],
            "emergency_suspected": True,
            "emergency_reason": "숨이 참",
            "model": "m",
        },
    ),
    "/llm/questions": (200, {"questions": [{"question_id": "q1", "text": "언제부터?"}]}),
    "/llm/explain": (200, {"explanation": "설명"}),
    "/safety/check": (
        200,
        {"is_emergency": True, "reasons": ["가슴 통증"], "rule_ids": ["chest_pain"]},
    ),
}


@pytest.fixture
def server():
    seen = []

    class Handler(BaseHTTPRequestHandler):
        routes: ClassVar[dict] = dict(ROUTES)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append((self.path, body))
            status, payload = self.routes[self.path]
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}", Handler, seen
    httpd.shutdown()


def test_clients_call_the_contract_endpoints(server):
    url, _, seen = server

    version, ranked = HttpMLClient(url).predict(["cough"], top_k=10)
    extracted = HttpLLMClient(url).extract_symptoms("기침이 나요")
    questions = HttpLLMClient(url).next_questions(["cough"])
    explanation = HttpLLMClient(url).explain(["폐렴"], ["cough"])
    reasons = HttpSafetyClient(url).check([{"symptom_id": "chest_pain"}])

    assert (version, ranked) == ("baseline-x", [("pneumonia", 0.6)])
    assert extracted.symptoms == [{"symptom_id": "cough"}] and extracted.emergency_suspected
    assert (
        questions[0]["text"] == "언제부터?" and explanation == "설명" and reasons == ["가슴 통증"]
    )
    assert dict(seen)["/predict"] == {"symptoms": [{"symptom_id": "cough"}], "top_k": 10}
    texts = [p for p, body in seen if "text" in body]
    assert texts == ["/llm/extract"]  # raw text goes only to /llm/extract


def test_503_becomes_service_unavailable_with_the_cause_code(server):
    url, handler, _ = server
    handler.routes["/llm/extract"] = (503, {"code": "llm_unavailable", "message": "x"})

    with pytest.raises(ServiceUnavailable) as exc:
        HttpLLMClient(url).extract_symptoms("기침")

    assert exc.value.code == "llm_unavailable"


def test_unreachable_service_is_service_unavailable():
    with pytest.raises(ServiceUnavailable) as exc:
        HttpMLClient("http://127.0.0.1:9", timeout=1).predict(["cough"], top_k=3)

    assert exc.value.code == "service_unavailable"
