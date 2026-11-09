from eval_tool.patient_metadata_scoring import aggregate_patient_metadata_scores


def test_aggregate_averages_sample_scores_and_pools_field_counts():
    scores = [
        {"fields": {"first_name": 1, "age": 0}, "score": 0.5},
        {"fields": {"first_name": 1, "last_name": 1, "age": 1, "pesel": 0}, "score": 0.75},
    ]

    result = aggregate_patient_metadata_scores(scores)

    assert result == {
        "samples": 2,
        "mean_score": 0.625,
        "fields": {
            "first_name": {"correct": 2, "graded": 2},
            "last_name": {"correct": 1, "graded": 1},
            "age": {"correct": 1, "graded": 2},
            "pesel": {"correct": 0, "graded": 1},
        },
    }


def test_aggregate_without_graded_samples_has_no_mean_score():
    assert aggregate_patient_metadata_scores([]) == {"samples": 0, "mean_score": None, "fields": {}}
