"""Offline evaluation of the on-screen rare-disease weight (mirrors backend screen_top3)."""

from triage.rare_weight_eval import screen_top3


def test_screen_top3_hides_sensitive_and_weights_rare_without_changing_probabilities():
    ranked = [("malaria", 0.375), ("aids", 0.33), ("hepatitis_a", 0.318), ("chicken_pox", 0.08)]

    shown = screen_top3(ranked, rare={"malaria"}, hidden={"aids"}, weight=0.3)

    assert shown == [("hepatitis_a", 0.318), ("malaria", 0.375), ("chicken_pox", 0.08)]


def test_weight_one_is_the_model_order():
    ranked = [("malaria", 0.375), ("hepatitis_a", 0.318), ("chicken_pox", 0.08)]

    assert screen_top3(ranked, rare={"malaria"}, hidden=set(), weight=1.0) == ranked
