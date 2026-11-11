from triage.data import RISK_FACTORS
from triage.e2e import evaluate_e2e
from triage.model import TriageModel

VOCAB = ["high_fever", "cough", "skin_rash", "itching", "nausea", *RISK_FACTORS]
MODEL = TriageModel.fit(
    [
        (frozenset({"high_fever", "cough"}), "pneumonia"),
        (frozenset({"skin_rash", "itching"}), "fungal_infection"),
        (frozenset({"nausea", "high_fever"}), "gastroenteritis"),
    ],
    VOCAB,
    version="test-0",
)
DEPARTMENTS = {
    "pneumonia": "01",
    "fungal_infection": "14",
    "gastroenteritis": "01",
    "typhoid": "01",
}


def case(disease, ids):
    return {"disease_id": disease, "extraction": {"symptoms": [{"symptom_id": i} for i in ids]}}


def test_e2e_top_k_and_department_accuracy():
    cases = [
        case("pneumonia", ["high_fever", "cough"]),  # top1 hit
        case("fungal_infection", ["skin_rash"]),  # top1 hit
        case("typhoid", ["nausea", "high_fever"]),  # disease miss, same department (01)
        case("pneumonia", []),  # LLM found nothing -> miss
    ]

    m = evaluate_e2e(MODEL, cases, DEPARTMENTS)

    assert m["cases"] == 4 and m["no_symptoms_extracted"] == 1
    assert m["top1"] == 0.5 and m["top3"] == 0.5
    assert m["department_top1"] == 0.75
