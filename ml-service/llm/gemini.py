"""GeminiProvider (T13). SDK: google-genai, https://github.com/googleapis/python-genai

- Structured output: response_mime_type="application/json" + response_json_schema
  (README "Pydantic Model Schema support"). A symptom_id enum of all 128 ids is
  rejected by the API (400 INVALID_ARGUMENT; 100 ids pass, anyOf split also
  fails, checked 2026-11-11), so ids are enforced by the prompt dictionary
  (risk factors excluded) and sanitize_symptoms() after parsing.
- Auth: GEMINI_API_KEY. In the cloud session a dummy value is enough; the
  network proxy injects the real key header.
- Free-tier data may be used by Google (SPEC 3.1): send no personal data.
"""

from __future__ import annotations

import json
import os
import time

from google import genai
from google.genai import errors, types

from llm.provider import (
    Extraction,
    filter_questions,
    load_symptom_dictionary,
    sanitize_explanation,
    sanitize_symptoms,
)
from triage.data import RISK_FACTORS

DEFAULT_MODEL = "gemini-3.5-flash-lite"

EXTRACT_INSTRUCTION = """너는 증상 안내 서비스의 증상 구조화 도우미다. 진단을 하지 않는다.
사용자가 한국어로 쓴 증상 문장에서, 아래 사전에 있는 증상만 골라 symptom_id로 돌려준다.
- 문장에 실제로 나온 증상만 고른다. 추측해서 더하지 않는다.
- 같은 뜻이면 사전의 동의어를 참고해 가장 가까운 하나를 고른다.
- "심하다", "참을 수 없다" 같은 표현이 있으면 severity를 severe로, 기간이 나오면 duration_days(오늘=0)를 채운다.
- 가슴 통증, 호흡곤란, 의식 저하, 한쪽 마비, 피를 토함처럼 위급할 수 있으면 emergency_suspected를 true로 하고 이유를 짧게 쓴다.
- 성 접촉, 주사·수혈 경로, 가족력 같은 위험 요인은 문장에 있어도 추출하지 않는다.
- 이름, 주소, 연락처 같은 개인정보는 다루지 않는다.

증상 사전 (symptom_id: 한국어명 (동의어)):
{dictionary}"""

QUESTIONS_INSTRUCTION = """너는 증상 안내 서비스의 추가 질문 도우미다. 진단을 하지 않는다.
이미 파악한 증상을 보고, 가능성 있는 질환을 가리는 데 도움이 되는 짧은 한국어 질문을 최대 3개 만든다.
발생 시점, 부위, 정도, 동반 증상을 묻는다. 선택지가 자연스러우면 choices를 붙인다.
성 접촉, 주사·수혈 경로, 가족력, 이름·주소·연락처는 절대 묻지 않는다."""

EXPLAIN_INSTRUCTION = """너는 증상 안내 서비스의 설명 도우미다. "진단"이라는 말을 쓰지 않는다.
가능성 있는 질환과 사용자의 증상을 보고, 일반인이 이해할 쉬운 한국어 2~3문장으로 설명한다.
확정적으로 말하지 말고, 언제 진료를 받아야 하는지 덧붙인다."""


class GeminiProvider:
    def __init__(
        self,
        client=None,
        model: str | None = None,
        vocab: dict[str, str] | None = None,
        max_retries: int = 3,
        retry_sleep: float = 20.0,
    ):
        self.client = client or genai.Client()
        self.model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self.vocab = {
            k: v for k, v in (vocab or load_symptom_dictionary()).items() if k not in RISK_FACTORS
        }
        self.max_retries = max_retries
        self.retry_sleep = retry_sleep

    def _generate(self, contents: str, config: types.GenerateContentConfig):
        """Returns the response; self.last_latency_s is the successful attempt only."""
        for attempt in range(self.max_retries + 1):
            start = time.perf_counter()
            try:
                response = self.client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
                self.last_latency_s = time.perf_counter() - start
                return response
            except errors.APIError as exc:
                # 429 quota and 5xx gateway/overload errors are temporary; others are real.
                if exc.code not in (429, 500, 502, 503, 504) or attempt == self.max_retries:
                    raise
                time.sleep(self.retry_sleep * 2**attempt)  # exponential backoff
        raise RuntimeError("unreachable")

    def _extract_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "symptoms": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "symptom_id": {"type": "string"},
                            "severity": {"type": "string", "enum": ["mild", "moderate", "severe"]},
                            "duration_days": {"type": "integer", "minimum": 0},
                        },
                        "required": ["symptom_id"],
                    },
                },
                "emergency_suspected": {"type": "boolean"},
                "emergency_reason": {"type": "string"},
            },
            "required": ["symptoms", "emergency_suspected"],
        }

    def extract_symptoms(self, text: str) -> Extraction:
        dictionary = "\n".join(f"{k}: {v}" for k, v in sorted(self.vocab.items()))
        config = types.GenerateContentConfig(
            system_instruction=EXTRACT_INSTRUCTION.format(dictionary=dictionary),
            response_mime_type="application/json",
            response_json_schema=self._extract_schema(),
            temperature=0,
        )
        response = self._generate(text, config)
        latency = self.last_latency_s  # excludes retry waits
        usage = getattr(response, "usage_metadata", None)
        tokens = {
            "prompt_tokens": getattr(usage, "prompt_token_count", 0) or 0,
            "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
        }
        try:
            data = json.loads(response.text or "")
        except ValueError:
            data = None
        if not isinstance(data, dict):
            return Extraction(symptoms=[], parsed=False, latency_s=latency, **tokens)
        return Extraction(
            symptoms=sanitize_symptoms(data.get("symptoms"), set(self.vocab)),
            emergency_suspected=bool(data.get("emergency_suspected")),
            emergency_reason=data.get("emergency_reason") or None,
            latency_s=latency,
            raw=data,
            **tokens,
        )

    def next_questions(self, symptom_ids: list[str]) -> list[dict]:
        names = [self.vocab.get(s, s).split(" (")[0] for s in symptom_ids]
        config = types.GenerateContentConfig(
            system_instruction=QUESTIONS_INSTRUCTION,
            response_mime_type="application/json",
            response_json_schema={
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question_id": {"type": "string"},
                                "text": {"type": "string"},
                                "choices": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["question_id", "text"],
                        },
                    }
                },
                "required": ["questions"],
            },
            temperature=0.2,
        )
        response = self._generate("파악한 증상: " + ", ".join(names), config)
        try:
            questions = json.loads(response.text or "").get("questions", [])
        except (ValueError, AttributeError):
            return []
        return filter_questions(questions)

    def explain(self, disease_names: list[str], symptom_ids: list[str]) -> str:
        names = [self.vocab.get(s, s).split(" (")[0] for s in symptom_ids]
        config = types.GenerateContentConfig(
            system_instruction=EXPLAIN_INSTRUCTION, temperature=0.3
        )
        prompt = f"가능성 있는 질환: {', '.join(disease_names)}\n증상: {', '.join(names)}"
        response = self._generate(prompt, config)
        return sanitize_explanation(response.text)
