"""Testy metryk ewaluacji (STT + NER), używanych przez run_eval.py."""

from metrics import (
    cer,
    compare_entities,
    compute_stt_metrics,
    medical_term_recall,
    normalize_text,
    number_precision,
    number_recall,
    pesel_accuracy,
    wer,
)


def test_stt_metrics():
    assert wer("guz 3 cm", "guz 3 cm") == 0
    assert cer("guz 3 cm", "guz 3 cm") == 0
    assert number_recall("guz 3 cm i 4 cm", "guz 3 cm i 40 cm") == 0.5
    # Halucynowana liczba: wszystkie referencyjne obecne (recall=1), ale dodano zbędną (precision<1).
    assert number_recall("guz 3 cm", "guz 3 cm i 8 cm") == 1.0
    assert number_precision("guz 3 cm", "guz 3 cm i 8 cm") == 0.5
    spurious = compute_stt_metrics("guz 3 cm", "guz 3 cm i 8 cm")
    assert spurious["has_critical_error"] is False
    assert spurious["has_spurious_number"] is True
    assert medical_term_recall("Guz nerka 3 cm.", "Guz nerka 3 cm.") == 1.0
    assert medical_term_recall("Guz nerka 3 cm.", "Guz 3 cm.") == 0.5
    assert pesel_accuracy("PESEL 12345678901", "PESEL 12345678901") == 1.0
    assert pesel_accuracy("PESEL 12345678901", "PESEL 12345678902") == 0.0
    assert pesel_accuracy("Brak identyfikatora", "Brak identyfikatora") is None
    assert compute_stt_metrics(
        "Guz 3 cm PESEL 12345678901", "Guz 4 cm PESEL 12345678902"
    )["has_critical_error"] is True


def test_number_normalization():
    # "5,5 cm" to 2 tokeny (nie 3), a łańcuch wymiarów to 1 token.
    assert normalize_text("5,5 cm").split() == ["5.5", "cm"]
    assert normalize_text("materiał 3,5 x 3,0 x 3,5 cm.").split() == ["materiał", "3.5x3.0x3.5", "cm"]
    # Wariant główny ujednolica , vs . (WER=0); wariant strict karze różnicę formatu (WER>0).
    assert wer("materiał 5,5 cm", "materiał 5.5 cm") == 0.0
    assert wer("materiał 5,5 cm", "materiał 5.5 cm", unify_numbers=False) > 0.0


def test_error_flags_separated():
    # Zgubiony termin ≠ błąd krytyczny; liczby/PESEL poprawne.
    term_only = compute_stt_metrics("Guz nerka 3 cm.", "Guz 3 cm.")
    assert term_only["has_critical_error"] is False
    assert term_only["has_term_error"] is True
    # Błąd twardy (liczba) nie jest sygnalizowany jako błąd terminologii, jeśli terminy się zgadzają.
    hard_only = compute_stt_metrics("Guz 3 cm.", "Guz 4 cm.")
    assert hard_only["has_critical_error"] is True
    assert hard_only["has_term_error"] is False


def test_ner_metrics():
    empty = compare_entities({}, {})
    assert empty["overall"]["precision"] == 1.0
    assert empty["overall"]["recall"] == 1.0

    expected = {"patient": {"pesel": "12345678901"}}
    predicted = {"patient": {"pesel": "12345678901"}}
    assert compare_entities(expected, predicted)["patient"]["f1"] == 1.0

    hallucinated = compare_entities({}, {"components": [{"name": "nerka"}]})
    assert hallucinated["overall"]["precision"] == 0.0

    omitted = compare_entities({"components": [{"name": "nerka"}]}, {})
    assert omitted["overall"]["recall"] == 0.0

    lesion = compare_entities(
        {"lesions": [{"type": "guz", "features": ["martwica", "zwapnienia"]}]},
        {"lesions": [{"type": "guz", "features": ["martwica"]}]},
    )
    assert lesion["lesions"]["tp"] == 1
    assert lesion["lesions"]["fn"] == 1
