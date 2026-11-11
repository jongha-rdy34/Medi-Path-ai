import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.contract import validate
from triage.data import RISK_FACTORS
from triage.model import TriageModel

ML = "ml-service.openapi.yaml"
VOCAB = ["high_fever", "cough", "skin_rash", "itching", "nausea", *RISK_FACTORS]
ROWS = [
    (frozenset({"high_fever", "cough"}), "pneumonia"),
    (frozenset({"skin_rash", "itching"}), "fungal_infection"),
    (frozenset({"nausea", "high_fever"}), "gastroenteritis"),
]


@pytest.fixture
def client():
    with TestClient(app) as c:
        app.state.model = TriageModel.fit(ROWS, VOCAB, version="test-0")
        yield c


def test_predict_matches_contract(client):
    body = {"symptoms": [{"symptom_id": "high_fever", "duration_days": 1}, {"symptom_id": "cough"}]}

    res = client.post("/predict", json=body)

    assert res.status_code == 200
    data = res.json()
    validate(data, ML, "PredictResponse")
    assert data["model_version"] == "test-0"
    assert len(data["predictions"]) == 3 and data["predictions"][0]["disease_id"] == "pneumonia"
    probs = [p["probability"] for p in data["predictions"]]
    assert probs == sorted(probs, reverse=True)


def test_top_k_and_unknown_ids(client):
    body = {
        "symptoms": [{"symptom_id": "itching"}, {"symptom_id": "not_in_dictionary"}],
        "top_k": 1,
    }

    data = client.post("/predict", json=body).json()

    validate(data, ML, "PredictResponse")
    assert len(data["predictions"]) == 1 and data["unknown_symptom_ids"] == ["not_in_dictionary"]


def test_risk_factors_do_not_change_the_answer(client):
    base = [{"symptom_id": "nausea"}]
    with_risk = base + [{"symptom_id": r} for r in RISK_FACTORS]

    a = client.post("/predict", json={"symptoms": base}).json()["predictions"]
    b = client.post("/predict", json={"symptoms": with_risk}).json()["predictions"]

    assert a == b


@pytest.mark.parametrize(
    "body",
    [
        {"symptoms": []},
        {"symptoms": [{"symptom_id": "Bad-ID"}]},
        {"symptoms": [{"symptom_id": "cough"}], "top_k": 0},
        {"symptoms": [{"symptom_id": "cough"}], "text": "raw sentence is not accepted"},
    ],
)
def test_invalid_requests_return_contract_error(client, body):
    res = client.post("/predict", json=body)

    assert res.status_code == 422
    validate(res.json(), "openapi.yaml", "Error")
    assert res.json()["code"] == "validation_error"


def test_no_model_returns_503(client):
    app.state.model = None

    res = client.post("/predict", json={"symptoms": [{"symptom_id": "cough"}]})

    assert res.status_code == 503
    validate(res.json(), "openapi.yaml", "Error")
    assert res.json()["code"] == "model_not_loaded"


def test_health_stays_ok_without_model(client):
    app.state.model = None

    assert client.get("/health").json() == {"status": "ok"}
