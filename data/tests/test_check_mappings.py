import csv

import pytest
from check_mappings import (
    Mappings,
    check_contract_examples,
    check_mappings,
    check_raw_coverage,
    load_mappings,
    symptom_id_from_column,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("itching", "itching"),
        (" skin_rash", "skin_rash"),
        ("spotting_ urination", "spotting_urination"),
        ("foul_smell_of urine", "foul_smell_of_urine"),
        ("dischromic _patches", "dischromic_patches"),
        ("toxic_look_(typhos)", "toxic_look_typhos"),
        ("fluid_overload.1", "fluid_overload"),
    ],
)
def test_symptom_id_from_column_normalizes_kaggle_names(raw, expected):
    assert symptom_id_from_column(raw) == expected


def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


@pytest.fixture
def mappings_dir(tmp_path):
    d = tmp_path / "mappings"
    d.mkdir()
    write_csv(d / "departments.csv", ["code", "name_ko"], [["01", "내과"], ["14", "피부과"]])
    write_csv(
        d / "disease_department.csv",
        [
            "disease_id",
            "kaggle_label",
            "disease_name_ko",
            "department_code",
            "alt_department_codes",
            "source_url",
            "review_status",
        ],
        [
            ["gerd", "GERD", "위식도역류질환", "01", "", "https://example.org/gerd", "reviewed"],
            ["acne", "Acne", "여드름", "14", "01", "", "draft"],
        ],
    )
    write_csv(
        d / "symptoms.csv",
        ["symptom_id", "name_ko", "synonyms_ko"],
        [["itching", "가려움", "간지러움"], ["skin_rash", "피부 발진", "발진|두드러기"]],
    )
    return d


def test_valid_mappings_have_no_errors_and_warn_about_missing_sources(mappings_dir):
    errors, warnings = check_mappings(load_mappings(mappings_dir))

    assert errors == []
    assert any("acne" in w and "source_url" in w for w in warnings)


def test_unknown_department_code_is_an_error(mappings_dir):
    m = load_mappings(mappings_dir)
    m.diseases[0]["department_code"] = "99"

    errors, _ = check_mappings(m)

    assert any("gerd" in e and "99" in e for e in errors)


def test_duplicate_ids_and_shared_synonyms_are_errors(mappings_dir):
    m = load_mappings(mappings_dir)
    m.diseases.append(dict(m.diseases[0]))
    m.symptoms[1]["synonyms_ko"] = "발진|간지러움"

    errors, _ = check_mappings(m)

    assert any("duplicate disease_id" in e and "gerd" in e for e in errors)
    assert any("간지러움" in e for e in errors)


def test_raw_coverage_reports_unmapped_labels_and_columns(mappings_dir, tmp_path):
    raw = tmp_path / "raw" / "kaggle_disease_prediction"
    raw.mkdir(parents=True)
    write_csv(
        raw / "Training.csv",
        ["itching", "skin_rash", "chest_pain", "prognosis", ""],
        [["1", "0", "0", "GERD ", ""], ["0", "1", "1", "Heart attack", ""]],
    )

    errors = check_raw_coverage(load_mappings(mappings_dir), tmp_path / "raw")

    assert any("Heart attack" in e for e in errors)
    assert any("chest_pain" in e for e in errors)
    assert not any("GERD" in e for e in errors)


def test_contract_examples_must_use_known_ids(mappings_dir, tmp_path):
    contract = tmp_path / "openapi.yaml"
    contract.write_text(
        "examples:\n"
        "  - symptom_id: itching\n"
        "  - symptom_id: chest_pain\n"
        "  - disease_id: gerd\n"
        "  - disease_id: heart_attack\n"
        "  - code: '14'\n"
        "  - code: '24'\n"
    )

    errors = check_contract_examples(load_mappings(mappings_dir), [contract])

    assert sorted(errors) == sorted(
        [
            f"{contract.name}: unknown symptom_id 'chest_pain'",
            f"{contract.name}: unknown disease_id 'heart_attack'",
            f"{contract.name}: unknown department code '24'",
        ]
    )


def test_mappings_type_is_simple_container(mappings_dir):
    m = load_mappings(mappings_dir)
    assert isinstance(m, Mappings)
    assert {d["code"] for d in m.departments} == {"01", "14"}


def test_sensitive_diseases_must_exist_in_the_mapping(mappings_dir):
    from check_mappings import check_sensitive

    write_csv(
        mappings_dir / "sensitive_diseases.csv",
        ["disease_id", "reason"],
        [["gerd", "x"], ["aids", "y"]],
    )

    errors = check_sensitive(load_mappings(mappings_dir), mappings_dir / "sensitive_diseases.csv")

    assert errors == ["sensitive_diseases.csv: unknown disease_id 'aids'"]
