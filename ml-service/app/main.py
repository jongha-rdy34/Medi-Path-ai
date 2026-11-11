from fastapi import FastAPI

# Pattern from https://github.com/fastapi/fastapi/blob/master/README.md ("Create it")
app = FastAPI(title="symptom-care ml-service")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Contract: contracts/ml-service.openapi.yaml#/paths/~1health"""
    return {"status": "ok"}
