from triage.data import RISK_FACTORS
from triage.model import TriageModel, top_k_accuracy

VOCAB = ["fever", "cough", "rash", "itch", "nausea", *RISK_FACTORS]
ROWS = [
    (frozenset({"fever", "cough"}), "flu"),
    (frozenset({"fever", "cough", "nausea"}), "flu"),
    (frozenset({"rash", "itch"}), "eczema"),
    (frozenset({"rash", "itch", "fever"}), "eczema"),
    (frozenset({"nausea"}), "gastro"),
    (frozenset({"nausea", "fever"}), "gastro"),
]


def trained():
    return TriageModel.fit(ROWS, VOCAB, version="test-0")


def test_predict_returns_sorted_top_k_probabilities():
    preds, unknown = trained().predict(["fever", "cough"], top_k=2)

    assert preds[0][0] == "flu"
    assert len(preds) == 2 and unknown == []
    assert preds[0][1] >= preds[1][1] and all(0 <= p <= 1 for _, p in preds)


def test_unknown_symptoms_are_reported_and_ignored():
    preds, unknown = trained().predict(["rash", "not_a_symptom"], top_k=1)

    assert unknown == ["not_a_symptom"] and preds[0][0] == "eczema"


def test_risk_factors_never_change_the_prediction():
    model = trained()

    assert model.predict(["fever"], 3) == model.predict(["fever", *RISK_FACTORS], 3)


def test_save_and_load_round_trip(tmp_path):
    model = trained()
    path = model.save(tmp_path)

    loaded = TriageModel.load(path)

    assert loaded.version == "test-0" and loaded.predict(["itch"], 2) == model.predict(["itch"], 2)


def test_top_k_accuracy():
    assert top_k_accuracy(trained(), ROWS, k=3) == 1.0
