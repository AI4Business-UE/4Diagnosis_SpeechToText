from eval_tool.ner_scoring import aggregate_ner_scores, score_ner


def test_ner_scoring_matches_structured_entities_without_order_sensitive_fields():
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
    assert result["categories"]["components"]["fields"]["dim_x"] == {
        "true_positives": 1,
        "false_positives": 0,
        "false_negatives": 0,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
    }


def test_ner_scoring_ignores_unannotated_fields_but_counts_known_absence():
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


def test_aggregate_ner_scores_pools_field_counts_and_record_matches():
    expected = {
        "patient": {"age": 50},
        "components": [],
        "lesions": [],
        "fluid_samples": [],
    }
    exact = score_ner(expected, expected)
    missed = score_ner(
        expected,
        {"patient": {"age": None}, "components": [], "lesions": [], "fluid_samples": []},
    )

    aggregate = aggregate_ner_scores([exact, missed])

    assert aggregate["records"] == 2
    assert aggregate["exact_record_rate"] == 0.5
    assert aggregate["categories"]["patient"]["fields"]["age"]["false_negatives"] == 1
    assert aggregate["fields"]["patient.age"]["false_negatives"] == 1


def test_aggregate_ner_scores_leave_exact_rate_undefined_without_records():
    aggregate = aggregate_ner_scores([])

    assert aggregate["records"] == 0
    assert aggregate["exact_record_rate"] is None
