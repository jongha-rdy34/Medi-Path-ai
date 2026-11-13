"""ml-service: triage-model inference. Contract: contracts/ml-service.openapi.yaml

FastAPI patterns used (https://github.com/fastapi/fastapi, docs_src/):
- lifespan model loading: docs_src/events/tutorial003.py
- validation error override: docs_src/handling_errors/tutorial005.py
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from llm.provider import Extraction
from safety.red_flags import Observation
from safety.red_flags import check as red_flag_check
from triage.model import TriageModel

log = logging.getLogger("ml-service")

DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
DEFAULT_MODEL_VERSION = "baseline-2026.11.0"


def load_model() -> TriageModel | None:
    model_dir = Path(os.environ.get("MODEL_DIR", DEFAULT_MODEL_DIR))
    version = os.environ.get("MODEL_VERSION", DEFAULT_MODEL_VERSION)
    path = model_dir / f"{version}.joblib"
    if not path.exists():
        log.warning("model file not found: %s (run: python -m triage.train)", path)
        return None
    return TriageModel.load(path)


def load_llm():
    """GeminiProvider for the service: short retries (latency budget, SPEC p95 < 10 s),
    fallback model from GEMINI_FALLBACK_MODEL, slim prompt (LLM_CANDIDATE_K, default 30),
    per-call time limit (LLM_TIMEOUT_S, default 8 s; on timeout the fallback model answers)."""
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
        log.warning("GEMINI_API_KEY is not set; /llm/* will return 503")
        return None
    from llm.gemini import GeminiProvider

    return GeminiProvider(
        max_retries=1,
        retry_sleep=1.0,
        candidate_k=int(os.environ.get("LLM_CANDIDATE_K", "30")),
        timeout_s=float(os.environ.get("LLM_TIMEOUT_S", "8")),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = load_model()
    app.state.llm = load_llm()
    yield
    app.state.model = None
    app.state.llm = None


app = FastAPI(title="MediPath ml-service", lifespan=lifespan)


class SymptomObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symptom_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    severity: Literal["mild", "moderate", "severe"] | None = None
    duration_days: int | None = Field(default=None, ge=0)


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symptoms: list[SymptomObservation] = Field(min_length=1, max_length=30)
    top_k: int = Field(default=3, ge=1, le=10)


def error(status: int, code: str, message: str, details: list | None = None) -> JSONResponse:
    body = {"code": code, "message": message}
    if details:
        body["details"] = details
    return JSONResponse(status_code=status, content=body)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"field": ".".join(str(p) for p in e["loc"][1:]) or "body", "message": e["msg"]}
        for e in exc.errors()
    ]
    return error(422, "validation_error", "요청 값이 올바르지 않습니다.", details)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness only, so the compose stack starts before a model is trained."""
    return {"status": "ok"}


@app.post("/predict", response_model=None)
def predict(body: PredictRequest, request: Request) -> dict | JSONResponse:
    model: TriageModel | None = request.app.state.model
    if model is None:
        return error(503, "model_not_loaded", "모델이 아직 로드되지 않았습니다.")
    ids = [s.symptom_id for s in body.symptoms]
    predictions, unknown = model.predict(ids, top_k=body.top_k)
    return {
        "model_version": model.version,
        "predictions": [{"disease_id": d, "probability": p} for d, p in predictions],
        "unknown_symptom_ids": unknown,
    }


# --- LLM and red-flag endpoints (T30). Raw text is never logged. ---

SYMPTOM_ID = r"^[a-z][a-z0-9_]*$"


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=500)


class QuestionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symptom_ids: list[Annotated[str, Field(pattern=SYMPTOM_ID)]] = Field(max_length=30)


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disease_names: list[str] = Field(min_length=1, max_length=3)
    symptom_ids: list[Annotated[str, Field(pattern=SYMPTOM_ID)]] = Field(max_length=30)
    emergency: bool = False


class SafetyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symptoms: list[SymptomObservation] = Field(max_length=30)


def llm_unavailable(where: str, exc: Exception | None) -> JSONResponse:
    # Cause code only: never the request text (SPEC section 6).
    cause = (getattr(exc, "code", None) or type(exc).__name__) if exc else "not_configured"
    log.warning("llm_unavailable endpoint=%s cause=%s", where, cause)
    return error(503, "llm_unavailable", "증상 분석이 잠시 어렵습니다. 잠시 후 다시 시도해 주세요.")


def call_llm(request: Request, where: str, fn):
    llm = request.app.state.llm
    if llm is None:
        return None, llm_unavailable(where, None)
    try:
        return fn(llm), None
    # Any failure of the external LLM (APIError after retries and fallback, transport errors)
    # must become the contract 503, never a 500.
    except Exception as exc:  # noqa: BLE001
        return None, llm_unavailable(where, exc)


@app.post("/llm/extract", response_model=None)
def llm_extract(body: ExtractRequest, request: Request) -> dict | JSONResponse:
    result, failure = call_llm(request, "extract", lambda llm: llm.extract_symptoms(body.text))
    if failure:
        return failure
    ex: Extraction = result
    return {
        "symptoms": [
            {
                k: v
                for k, v in (
                    ("symptom_id", s.symptom_id),
                    ("severity", s.severity),
                    ("duration_days", s.duration_days),
                )
                if v is not None
            }
            for s in ex.symptoms
        ],
        "emergency_suspected": ex.emergency_suspected,
        "emergency_reason": ex.emergency_reason,
        "model": ex.served_model or getattr(request.app.state.llm, "model", "unknown"),
    }


@app.post("/llm/questions", response_model=None)
def llm_questions(body: QuestionsRequest, request: Request) -> dict | JSONResponse:
    result, failure = call_llm(
        request, "questions", lambda llm: llm.next_questions(body.symptom_ids)
    )
    return failure or {"questions": result[:3]}


@app.post("/llm/explain", response_model=None)
def llm_explain(body: ExplainRequest, request: Request) -> dict | JSONResponse:
    result, failure = call_llm(
        request,
        "explain",
        lambda llm: llm.explain(body.disease_names, body.symptom_ids, body.emergency),
    )
    return failure or {"explanation": result}


@app.post("/safety/check")
def safety_check(body: SafetyRequest) -> dict:
    result = red_flag_check([Observation(s.symptom_id, s.severity) for s in body.symptoms])
    return {
        "is_emergency": result.is_emergency,
        "reasons": result.reasons,
        "rule_ids": result.rule_ids,
    }
