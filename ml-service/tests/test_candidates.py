from llm.candidates import ALWAYS_INCLUDE, select_candidates
from llm.provider import load_symptom_dictionary
from triage.data import RISK_FACTORS

VOCAB = load_symptom_dictionary()


def test_relevant_symptoms_are_selected_from_korean_wording():
    picked = select_candidates("어제부터 열이 나고 기침과 누런 가래가 나와요", VOCAB, k=30)

    assert {"high_fever", "cough", "phlegm"} <= set(picked)


def test_candidate_list_is_bounded_and_keeps_emergency_symptoms():
    picked = select_candidates("무릎이 아파요", VOCAB, k=20)

    assert len(picked) <= 20 + len(ALWAYS_INCLUDE)
    assert set(ALWAYS_INCLUDE) <= set(picked)
    assert "knee_pain" in picked


def test_never_offers_risk_factors_or_unknown_ids():
    picked = select_candidates("가족 중에 같은 병이 있고 주사를 맞았어요", VOCAB, k=30)

    assert not set(picked) & set(RISK_FACTORS)
    assert set(picked) <= set(VOCAB)


def test_always_include_ids_exist_in_the_dictionary():
    assert set(ALWAYS_INCLUDE) <= set(VOCAB)


def test_dictionary_location_can_be_overridden_for_containers(tmp_path, monkeypatch):
    import importlib

    from llm import provider

    (tmp_path / "symptoms.csv").write_text(
        "symptom_id,name_ko,synonyms_ko\ncough,기침,콜록\n", encoding="utf-8"
    )
    monkeypatch.setenv("MAPPINGS_DIR", str(tmp_path))
    try:
        assert importlib.reload(provider).load_symptom_dictionary() == {"cough": "기침 (콜록)"}
    finally:
        monkeypatch.delenv("MAPPINGS_DIR")
        importlib.reload(provider)
