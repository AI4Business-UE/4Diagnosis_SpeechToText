from eval_tool.transcript_scoring import aggregate_transcript_scores


def test_transcript_aggregation_pools_edits_and_reference_lengths():
    aggregate = aggregate_transcript_scores(
        [
            {"word_errors": 1, "reference_words": 3, "character_errors": 2, "reference_characters": 10},
            {"word_errors": 1, "reference_words": 2, "character_errors": 4, "reference_characters": 9},
        ]
    )

    assert aggregate["wer"] == 2 / 5
    assert aggregate["cer"] == 6 / 19
    assert aggregate["samples"] == 2


def test_transcript_aggregation_leaves_rates_undefined_without_scored_samples():
    aggregate = aggregate_transcript_scores([])

    assert aggregate["samples"] == 0
    assert aggregate["wer"] is None
    assert aggregate["cer"] is None
