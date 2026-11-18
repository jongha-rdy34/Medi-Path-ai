"""The AI stubs used by E2E (TRIAGE_CLIENTS=stub) follow the demo sentence (docs/demo/scenarios.md)."""

from triage.clients import StubLLMClient, StubMLClient

DEMO = "몸에 가려운 발진이 오돌토돌 올라오고 피부에 얼룩덜룩한 반점이 생겼어요"


def test_stub_extracts_the_demo_skin_symptoms():
    ids = [s["symptom_id"] for s in StubLLMClient().extract_symptoms(DEMO).symptoms]

    assert ids == ["itching", "skin_rash", "dischromic_patches"]


def test_stub_ranks_the_demo_like_the_real_model():
    _, ranked = StubMLClient().predict(["itching", "skin_rash", "dischromic_patches"], top_k=3)

    assert [d for d, _ in ranked] == ["fungal_infection", "drug_reaction", "chicken_pox"]
    assert ranked[0][1] >= 0.7  # shown as "가능성 높음"
