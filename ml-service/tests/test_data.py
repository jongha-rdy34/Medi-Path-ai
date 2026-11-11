import pytest

from triage.data import (
    RISK_FACTORS,
    dedupe,
    group_split,
    make_noise_set,
    symptom_id_from_column,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("spotting_ urination", "spotting_urination"),
        ("toxic_look_(typhos)", "toxic_look_typhos"),
        ("fluid_overload.1", "fluid_overload"),
        (" skin_rash", "skin_rash"),
    ],
)
def test_symptom_id_from_column_matches_data_foundation_rule(raw, expected):
    # Same rule as data/scripts/check_mappings.py (T11)
    assert symptom_id_from_column(raw) == expected


def rows_for(disease, combos):
    return [(frozenset(c), disease) for c in combos]


def test_dedupe_keeps_one_row_per_combination_and_disease():
    rows = rows_for("flu", [{"a", "b"}, {"a", "b"}, {"a"}])

    assert sorted(dedupe(rows), key=lambda r: sorted(r[0])) == rows_for("flu", [{"a"}, {"a", "b"}])


def test_group_split_never_shares_a_combination_and_covers_every_disease():
    rows = rows_for("flu", [{"a", str(i)} for i in range(6)]) + rows_for(
        "cold", [{"b", str(i)} for i in range(5)]
    )

    train, val, test = group_split(rows, seed=7)

    combos = [{r[0] for r in part} for part in (train, val, test)]
    assert not (combos[0] & combos[1] or combos[0] & combos[2] or combos[1] & combos[2])
    assert len(train) + len(val) + len(test) == len(rows)
    for part in (train, val, test):
        assert {d for _, d in part} == {"flu", "cold"}
    assert group_split(rows, seed=7) == (train, val, test)


def test_noise_set_is_seeded_nonempty_and_never_adds_risk_factors():
    rows = rows_for("flu", [{"a", "b", "c", "d"}])
    vocab = ["a", "b", "c", "d", "e", "f", *RISK_FACTORS]

    noisy = make_noise_set(rows, vocab, seed=3, variants=20)

    assert noisy == make_noise_set(rows, vocab, seed=3, variants=20)
    assert len(noisy) == 20
    assert all(len(s) >= 2 and d == "flu" for s, d in noisy)
    assert all(not (s & set(RISK_FACTORS)) for s, _ in noisy)
    assert any(s != rows[0][0] for s, _ in noisy)
