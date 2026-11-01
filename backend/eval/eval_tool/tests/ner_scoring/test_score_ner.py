from eval_tool.ner_scoring import score_ner


def test_ner_score_handles_unit_equivalence_and_unordered_entities():
    expected = {
        "patient": {"first_name": "Anna", "last_name": "Nowak"},
        "components": [
            {"name": "nerka", "dim_x": 1.0, "unit": "cm"},
            {"name": "moczowód", "length": 2.0, "unit": "cm"},
        ],
        "lesions": [],
        "fluid_samples": [],
    }
    actual = {
        "patient": {"first_name": "Anna", "last_name": "Nowak", "pesel": None, "age": None},
        "components": [
            {"name": "moczowód", "length": 20.0, "unit": "mm"},
            {"name": "NERKA", "dim_x": 10.0, "unit": "mm", "description": None},
        ],
        "lesions": [],
        "fluid_samples": [],
    }

    result = score_ner(expected, actual)

    assert result["exact_record_match"] is True
    assert result["categories"]["components"]["fields"]["dim_x"]["f1"] == 1.0


def test_ner_score_ignores_unknown_fields_but_counts_known_absence():
    expected = {
        "patient": {"first_name": "Anna", "last_name": None},
        "components": [],
        "lesions": [],
        "fluid_samples": [],
    }
    actual = {
        "patient": {"first_name": "Anna", "last_name": "Nowak", "pesel": "123", "age": None},
        "components": [{"name": "nerka"}],
        "lesions": [],
        "fluid_samples": [],
    }

    result = score_ner(expected, actual)

    assert result["exact_record_match"] is False
    assert result["categories"]["patient"]["fields"]["first_name"]["f1"] == 1.0
    assert result["categories"]["patient"]["fields"]["last_name"]["false_positives"] == 1
    assert result["categories"]["components"]["entity_counts"]["false_positives"] == 1


def test_ner_score_uses_global_matching_instead_of_greedy_pairs():
    expected = {
        "patient": {"first_name": None, "last_name": None, "pesel": None, "age": None},
        "components": [
            {"name": "A", "description": "X", "count": 2, "dim_x": 5, "unit": "cm"},
            {"name": "B", "description": "X", "count": 3},
        ],
        "lesions": [],
        "fluid_samples": [],
    }
    actual = {
        "patient": {"first_name": None, "last_name": None, "pesel": None, "age": None},
        "components": [
            {"name": "A", "description": "X", "count": 3, "dim_x": 5, "unit": "cm"},
            {"name": "A", "description": "Y", "count": 2, "unit": "cm"},
        ],
        "lesions": [],
        "fluid_samples": [],
    }

    result = score_ner(expected, actual)
    counts = result["categories"]["components"]["fields"]["count"]

    assert counts["true_positives"] == 2
    assert counts["false_positives"] == 0
    assert counts["false_negatives"] == 0
