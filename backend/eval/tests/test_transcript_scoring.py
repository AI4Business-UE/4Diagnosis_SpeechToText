from eval_tool.transcript_scoring import (aggregate_transcript_scores,
                                          score_transcript)


def test_transcript_scoring_ignores_case_punctuation_and_whitespace():
    score = score_transcript(
        "Zażółć gęślą, jaźń!",
        "  ZAŻÓŁĆ   gęślą jaźń  ",
    )

    assert score["wer"] == 0
    assert score["cer"] == 0


def test_transcript_scoring_preserves_polish_diacritics_and_word_forms():
    score = score_transcript("Zażółć gęślą jaźń", "Zazolc gesla jazn")

    assert score["word_errors"] > 0
    assert score["wer"] == 1


def test_transcript_scoring_reports_word_and_character_error_rates():
    score = score_transcript("kot ma psa", "kot miał psa")

    assert score["word_errors"] == 1
    assert score["reference_words"] == 3
    assert score["wer"] == 1 / 3
    assert score["cer"] == 2 / 10


def test_aggregate_transcript_scores_pools_edits_and_reference_lengths():
    aggregate = aggregate_transcript_scores(
        [
            score_transcript("kot ma psa", "kot miał psa"),
            score_transcript("duży pies", "duży kot"),
        ]
    )

    assert aggregate["wer"] == 2 / 5
    assert aggregate["cer"] == 6 / 19
    assert aggregate["samples"] == 2


def test_aggregate_transcript_scores_leave_rates_undefined_without_scored_samples():
    aggregate = aggregate_transcript_scores([])

    assert aggregate["samples"] == 0
    assert aggregate["wer"] is None
    assert aggregate["cer"] is None
