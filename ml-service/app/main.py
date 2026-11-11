"""ml-service: triage-model inference. Contract: contracts/ml-service.openapi.yaml

FastAPI patterns used (https://github.com/fastapi/fastapi, docs_src/):
- lifespan model loading: docs_src/events/tutorial003.py
- validation error override: docs_src/handling_errors/tutorial005.py
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = load_model()
    yield
    app.state.model = None


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
