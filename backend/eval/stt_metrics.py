from __future__ import annotations

import importlib.util
import re
import string
from pathlib import Path


PUNCT_TRANSLATION = str.maketrans({char: " " for char in string.punctuation})
NUMBER_PATTERN = re.compile(r"\d+(?:[,.]\d+)?")
DIMENSION_PATTERN = re.compile(
    r"\d+(?:[,.]\d+)?(?:\s*[x×]\s*\d+(?:[,.]\d+)?)+\s*(?:mm|cm|m)?|"
    r"\d+(?:[,.]\d+)?\s*(?:mm|cm|m)"
)
PESEL_PATTERN = re.compile(r"\b\d{11}\b")
REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_medical_terms() -> list[str]:
    dictionary_path = REPO_ROOT / "backend/src/app_stt/data/macro_dictionary.py"
    spec = importlib.util.spec_from_file_location("eval_macro_dictionary", dictionary_path)
    if spec is None or spec.loader is None:
        return []

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dictionary = getattr(module, "MEDICAL_NOMENCLATURE_DICTIONARY", {})

    terms = []
    for values in dictionary.values():
        terms.extend(values)

    return sorted({normalize_text(term) for term in terms if normalize_text(term)}, key=len, reverse=True)


def normalize_text(text: str) -> str:
    text = str(text or "").lower()
    text = text.replace("×", "x")
    text = text.translate(PUNCT_TRANSLATION)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


MEDICAL_TERMS = _load_medical_terms()


def _edit_distance(left: list[str] | str, right: list[str] | str) -> int:
    left_len = len(left)
    right_len = len(right)

    previous = list(range(right_len + 1))
    for i in range(1, left_len + 1):
        current = [i] + [0] * right_len
        for j in range(1, right_len + 1):
            substitution_cost = 0 if left[i - 1] == right[j - 1] else 1
            current[j] = min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + substitution_cost,
            )
        previous = current

    return previous[right_len]


def wer(reference: str, hypothesis: str) -> float:
    ref_words = normalize_text(reference).split()
    hyp_words = normalize_text(hypothesis).split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    return _edit_distance(ref_words, hyp_words) / len(ref_words)


def cer(reference: str, hypothesis: str) -> float:
    ref_chars = normalize_text(reference).replace(" ", "")
    hyp_chars = normalize_text(hypothesis).replace(" ", "")
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    return _edit_distance(ref_chars, hyp_chars) / len(ref_chars)


def _canonical_values(pattern: re.Pattern[str], text: str) -> list[str]:
    values = []
    for match in pattern.findall(str(text or "").lower()):
        value = re.sub(r"\s+", "", match)
        values.append(value.replace(",", ".").replace("×", "x"))
    return values


def recall(reference_values: list[str], hypothesis_values: list[str]) -> float | None:
    if not reference_values:
        return None

    remaining = list(hypothesis_values)
    matched = 0
    for value in reference_values:
        if value in remaining:
            matched += 1
            remaining.remove(value)

    return matched / len(reference_values)


def _phrase_present(phrase: str, text: str) -> bool:
    return bool(re.search(rf"(^|\s){re.escape(phrase)}($|\s)", text))


def number_recall(reference: str, hypothesis: str) -> float | None:
    return recall(
        _canonical_values(NUMBER_PATTERN, reference),
        _canonical_values(NUMBER_PATTERN, hypothesis),
    )


def dimension_recall(reference: str, hypothesis: str) -> float | None:
    return recall(
        _canonical_values(DIMENSION_PATTERN, reference),
        _canonical_values(DIMENSION_PATTERN, hypothesis),
    )


def medical_term_recall(reference: str, hypothesis: str) -> float | None:
    normalized_reference = normalize_text(reference)
    normalized_hypothesis = normalize_text(hypothesis)
    reference_terms = [
        term for term in MEDICAL_TERMS
        if _phrase_present(term, normalized_reference)
    ]
    hypothesis_terms = [
        term for term in reference_terms
        if _phrase_present(term, normalized_hypothesis)
    ]

    return recall(reference_terms, hypothesis_terms)


def pesel_accuracy(reference: str, hypothesis: str) -> float | None:
    reference_pesels = PESEL_PATTERN.findall(str(reference or ""))
    if not reference_pesels:
        return None

    hypothesis_pesels = PESEL_PATTERN.findall(str(hypothesis or ""))
    return 1.0 if reference_pesels == hypothesis_pesels else 0.0


def _is_recall_error(value: float | None) -> bool:
    return value is not None and value < 1.0


def compute_stt_metrics(reference: str, hypothesis: str) -> dict[str, float | int | bool | None]:
    metrics = {
        "wer": wer(reference, hypothesis),
        "cer": cer(reference, hypothesis),
        "number_recall": number_recall(reference, hypothesis),
        "dimension_recall": dimension_recall(reference, hypothesis),
        "medical_term_recall": medical_term_recall(reference, hypothesis),
        "pesel_accuracy": pesel_accuracy(reference, hypothesis),
    }

    critical_checks = [
        metrics["number_recall"],
        metrics["dimension_recall"],
        metrics["medical_term_recall"],
        metrics["pesel_accuracy"],
    ]
    critical_error_count = sum(1 for value in critical_checks if _is_recall_error(value))
    metrics["critical_error_count"] = critical_error_count
    metrics["has_critical_error"] = critical_error_count > 0

    return metrics


def _self_check() -> None:
    assert wer("guz 3 cm", "guz 3 cm") == 0
    assert cer("guz 3 cm", "guz 3 cm") == 0
    assert number_recall("guz 3 cm i 4 cm", "guz 3 cm i 40 cm") == 0.5
    assert medical_term_recall("Guz nerka 3 cm.", "Guz nerka 3 cm.") == 1.0
    assert medical_term_recall("Guz nerka 3 cm.", "Guz 3 cm.") == 0.5
    assert pesel_accuracy("PESEL 12345678901", "PESEL 12345678901") == 1.0
    assert pesel_accuracy("PESEL 12345678901", "PESEL 12345678902") == 0.0
    assert pesel_accuracy("Brak identyfikatora", "Brak identyfikatora") is None
    assert compute_stt_metrics("Guz 3 cm PESEL 12345678901", "Guz 4 cm PESEL 12345678902")["has_critical_error"] is True


if __name__ == "__main__":
    _self_check()
    print("STT metrics self-check passed")
