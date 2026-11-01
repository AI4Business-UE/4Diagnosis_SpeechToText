from eval_tool.ner_scoring import aggregate_ner_scores


def test_ner_aggregation_pools_field_counts_and_record_matches():
    one_record = {
        "exact_record_match": True,
        "categories": {
            "patient": {
                "entity_counts": {"true_positives": 1, "false_positives": 0, "false_negatives": 0},
                "fields": {"age": {"true_positives": 1, "false_positives": 0, "false_negatives": 0}},
            },
            "components": {"entity_counts": {"true_positives": 0, "false_positives": 0, "false_negatives": 0}, "fields": {}},
            "lesions": {"entity_counts": {"true_positives": 0, "false_positives": 0, "false_negatives": 0}, "fields": {}},
            "fluid_samples": {"entity_counts": {"true_positives": 0, "false_positives": 0, "false_negatives": 0}, "fields": {}},
        },
    }
    one_miss = {
        "exact_record_match": False,
        "categories": {
            "patient": {
                "entity_counts": {"true_positives": 0, "false_positives": 0, "false_negatives": 1},
                "fields": {"age": {"true_positives": 0, "false_positives": 0, "false_negatives": 1}},
            },
            "components": {"entity_counts": {"true_positives": 0, "false_positives": 0, "false_negatives": 0}, "fields": {}},
            "lesions": {"entity_counts": {"true_positives": 0, "false_positives": 0, "false_negatives": 0}, "fields": {}},
            "fluid_samples": {"entity_counts": {"true_positives": 0, "false_positives": 0, "false_negatives": 0}, "fields": {}},
        },
    }

    aggregate = aggregate_ner_scores([one_record, one_miss])

    assert aggregate["records"] == 2
    assert aggregate["exact_record_rate"] == 0.5
    assert aggregate["categories"]["patient"]["fields"]["age"]["false_negatives"] == 1
    assert aggregate["fields"]["patient.age"]["false_negatives"] == 1


def test_ner_aggregation_leaves_exact_rate_undefined_without_records():
    aggregate = aggregate_ner_scores([])

    assert aggregate["records"] == 0
    assert aggregate["exact_record_rate"] is None
