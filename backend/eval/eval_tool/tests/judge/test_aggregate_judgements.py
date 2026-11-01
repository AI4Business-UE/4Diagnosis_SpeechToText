from eval_tool.judge import aggregate_judgements


def test_judge_aggregation_reports_mean_distribution_and_issue_counts():
    aggregate = aggregate_judgements(
        [
            {"score": 4, "omissions": [], "additions": [], "contradictions": [], "rationale": ""},
            {"score": 2, "omissions": ["x"], "additions": ["y"], "contradictions": [], "rationale": ""},
        ]
    )

    assert aggregate["mean_score"] == 3
    assert aggregate["score_distribution"] == {"0": 0, "1": 0, "2": 1, "3": 0, "4": 1}
    assert aggregate["samples_with_omissions"] == 1
    assert aggregate["samples_with_additions"] == 1
