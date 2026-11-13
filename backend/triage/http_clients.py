"""HTTP clients for ml-service (contracts/ml-service.openapi.yaml), stdlib only.

Raw text is sent only to POST /llm/extract. Any failure (HTTP error, timeout,
connection refused) becomes ServiceUnavailable carrying a cause code, never the
request body.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from triage.clients import Extracted


class ServiceUnavailable(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _post(base_url: str, path: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as exc:
        try:
            code = json.loads(exc.read()).get("code") or f"http_{exc.code}"
        except ValueError:
            code = f"http_{exc.code}"
        raise ServiceUnavailable(code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ServiceUnavailable("service_unavailable") from None


class _Base:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url
        self.timeout = timeout


class HttpLLMClient(_Base):
    def extract_symptoms(self, text: str) -> Extracted:
        data = _post(self.base_url, "/llm/extract", {"text": text}, self.timeout)
        return Extracted(
            symptoms=data["symptoms"],
            emergency_suspected=data["emergency_suspected"],
            emergency_reason=data.get("emergency_reason"),
        )

    def next_questions(self, symptom_ids: list[str]) -> list[dict]:
        return _post(self.base_url, "/llm/questions", {"symptom_ids": symptom_ids}, self.timeout)[
            "questions"
        ]

    def explain(self, disease_names: list[str], symptom_ids: list[str]) -> str:
        body = {"disease_names": disease_names, "symptom_ids": symptom_ids}
        return _post(self.base_url, "/llm/explain", body, self.timeout)["explanation"]


class HttpMLClient(_Base):
    def predict(
        self, symptom_ids: list[str], top_k: int = 3
    ) -> tuple[str, list[tuple[str, float]]]:
        body = {"symptoms": [{"symptom_id": s} for s in symptom_ids], "top_k": top_k}
        data = _post(self.base_url, "/predict", body, self.timeout)
        return data["model_version"], [
            (p["disease_id"], p["probability"]) for p in data["predictions"]
        ]


class HttpSafetyClient(_Base):
    def check(self, symptoms: list[dict]) -> list[str]:
        return _post(self.base_url, "/safety/check", {"symptoms": symptoms}, self.timeout)[
            "reasons"
        ]
