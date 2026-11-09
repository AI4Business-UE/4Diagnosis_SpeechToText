from eval_tool.transcript_scoring import score_transcript


def test_transcript_score_ignores_case_punctuation_and_whitespace():
    score = score_transcript("Zażółć gęślą, jaźń!", "  ZAŻÓŁĆ   gęślą jaźń  ")

    assert score["wer"] == 0
    assert score["cer"] == 0


def test_transcript_score_preserves_polish_diacritics_and_word_forms():
    score = score_transcript("Zażółć gęślą jaźń", "Zazolc gesla jazn")

    assert score["word_errors"] > 0
    assert score["wer"] == 1


def test_transcript_score_reports_word_and_character_error_rates():
    score = score_transcript("kot ma psa", "kot miał psa")

    assert score["word_errors"] == 1
    assert score["reference_words"] == 3
    assert score["wer"] == 1 / 3
    assert score["cer"] == 2 / 10
