"""Metryki ewaluacji: STT (WER/CER, liczby, wymiary, terminy medyczne, PESEL)
oraz NER (precision/recall/f1 per encja). Scalone z dawnych stt/metrics.py i
ner/metrics.py w jeden moduł używany przez run_eval.py."""

from __future__ import annotations

import importlib.util
import json
import math
import re
import string
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


# ══════════════════════════════════════════════════════════════════════════════
# STT
# ══════════════════════════════════════════════════════════════════════════════

_SENTENCE_PUNCT = "".join(char for char in string.punctuation if char not in ".,")
PUNCT_TRANSLATION = str.maketrans({char: " " for char in _SENTENCE_PUNCT})
# usuwa . oraz , tylko gdy NIE stoją między dwiema cyframi (kropki zdaniowe, przecinki na końcu słowa)
BOUNDARY_DOTCOMMA_PATTERN = re.compile(r"(?<!\d)[.,]|[.,](?!\d)")
# ujednolica zapis wymiarów: "3,5 x 3,0" -> "3,5x3,0" (lookaround nie zjada cyfr, więc działa dla łańcuchów AxBxC)
DIMENSION_SPACING_PATTERN = re.compile(r"(?<=\d)\s*x\s*(?=\d)")
NUMBER_PATTERN = re.compile(r"\d+(?:[,.]\d+)?")
DIMENSION_PATTERN = re.compile(
    r"\d+(?:[,.]\d+)?(?:\s*[x×]\s*\d+(?:[,.]\d+)?)+\s*(?:mm|cm|m)?|"
    r"\d+(?:[,.]\d+)?\s*(?:mm|cm|m)"
)
PESEL_PATTERN = re.compile(r"\b\d{11}\b")


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


def normalize_text(text: str, unify_numbers: bool = True) -> str:
    text = str(text or "").lower()
    text = text.replace("×", "x")
    text = text.translate(PUNCT_TRANSLATION)
    text = BOUNDARY_DOTCOMMA_PATTERN.sub(" ", text)
    text = DIMENSION_SPACING_PATTERN.sub("x", text)
    if unify_numbers:
        text = text.replace(",", ".")
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


def wer(reference: str, hypothesis: str, unify_numbers: bool = True) -> float:
    ref_words = normalize_text(reference, unify_numbers).split()
    hyp_words = normalize_text(hypothesis, unify_numbers).split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    return _edit_distance(ref_words, hyp_words) / len(ref_words)


def cer(reference: str, hypothesis: str, unify_numbers: bool = True) -> float:
    ref_chars = normalize_text(reference, unify_numbers).replace(" ", "")
    hyp_chars = normalize_text(hypothesis, unify_numbers).replace(" ", "")
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


def precision(reference_values: list[str], hypothesis_values: list[str]) -> float | None:
    """Lustro `recall`: jaka część wartości z hipotezy ma pokrycie w referencji.
    Wychwytuje wartości halucynowane (dorzucone przez model), których recall nie karze."""
    if not hypothesis_values:
        return None

    remaining = list(reference_values)
    matched = 0
    for value in hypothesis_values:
        if value in remaining:
            matched += 1
            remaining.remove(value)

    return matched / len(hypothesis_values)


def _phrase_present(phrase: str, text: str) -> bool:
    return bool(re.search(rf"(^|\s){re.escape(phrase)}($|\s)", text))


def number_recall(reference: str, hypothesis: str) -> float | None:
    return recall(
        _canonical_values(NUMBER_PATTERN, reference),
        _canonical_values(NUMBER_PATTERN, hypothesis),
    )


def number_precision(reference: str, hypothesis: str) -> float | None:
    return precision(
        _canonical_values(NUMBER_PATTERN, reference),
        _canonical_values(NUMBER_PATTERN, hypothesis),
    )


def dimension_recall(reference: str, hypothesis: str) -> float | None:
    return recall(
        _canonical_values(DIMENSION_PATTERN, reference),
        _canonical_values(DIMENSION_PATTERN, hypothesis),
    )


def dimension_precision(reference: str, hypothesis: str) -> float | None:
    return precision(
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
        "wer_strict": wer(reference, hypothesis, unify_numbers=False),
        "cer_strict": cer(reference, hypothesis, unify_numbers=False),
        "number_recall": number_recall(reference, hypothesis),
        "number_precision": number_precision(reference, hypothesis),
        "dimension_recall": dimension_recall(reference, hypothesis),
        "dimension_precision": dimension_precision(reference, hypothesis),
        "medical_term_recall": medical_term_recall(reference, hypothesis),
        "pesel_accuracy": pesel_accuracy(reference, hypothesis),
    }

    # Twarde błędy krytyczne (exact-match, wysoka stawka): liczby, wymiary, PESEL.
    # Recall-based: sygnalizuje ZGUBIONE wartości krytyczne.
    hard_critical_checks = [
        metrics["number_recall"],
        metrics["dimension_recall"],
        metrics["pesel_accuracy"],
    ]
    critical_error_count = sum(1 for value in hard_critical_checks if _is_recall_error(value))
    metrics["critical_error_count"] = critical_error_count
    metrics["has_critical_error"] = critical_error_count > 0

    # Precision-based: sygnalizuje DODANE (halucynowane) liczby, których recall nie łapie.
    metrics["has_spurious_number"] = _is_recall_error(metrics["number_precision"])

    # Terminologia medyczna — kategoria miękka, śledzona osobno.
    metrics["has_term_error"] = _is_recall_error(metrics["medical_term_recall"])

    return metrics


# ══════════════════════════════════════════════════════════════════════════════
# NER
# ══════════════════════════════════════════════════════════════════════════════

ENTITY_FIELDS = {
    "patient": ["first_name", "last_name", "pesel", "age"],
    "components": ["name", "count", "dim_x", "dim_y", "dim_z", "length", "diameter", "unit", "description"],
    "lesions": [
        "type",
        "dim_x",
        "dim_y",
        "dim_z",
        "diameter",
        "length",
        "unit",
        "color",
        "structure",
        "features",
        "infiltration",
        "location_description",
        "organ",
        "shape",
        "borders",
        "additional_notes",
        "component_index",
    ],
    "fluid_samples": ["source", "material_type", "volume_ml", "color", "clarity", "consistency", "fixation"],
}

NUMERIC_FIELDS = {
    "age",
    "count",
    "dim_x",
    "dim_y",
    "dim_z",
    "length",
    "diameter",
    "volume_ml",
    "component_index",
}


def parse_entities(value: str | dict | None) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if not str(value).strip():
        return {}
    return json.loads(value)


def _is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def _normalize_entity_text(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace("×", "x").replace(",", ".")
    text = re.sub(r"[^\wąćęłńóśźż.]+", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_number(value: Any) -> float | None:
    if _is_empty(value):
        return None
    try:
        number = float(str(value).replace(",", "."))
    except ValueError:
        return None
    return number


def _values_match(field: str, expected: Any, predicted: Any) -> bool:
    if field == "features":
        expected_set = {_normalize_entity_text(item) for item in expected or [] if not _is_empty(item)}
        predicted_set = {_normalize_entity_text(item) for item in predicted or [] if not _is_empty(item)}
        return expected_set == predicted_set

    if field in NUMERIC_FIELDS:
        expected_number = _normalize_number(expected)
        predicted_number = _normalize_number(predicted)
        if expected_number is None or predicted_number is None:
            return expected_number == predicted_number
        return math.isclose(expected_number, predicted_number, rel_tol=0.0, abs_tol=0.001)

    return _normalize_entity_text(expected) == _normalize_entity_text(predicted)


def _filled_fields(entity: dict, fields: list[str]) -> list[str]:
    return [field for field in fields if not _is_empty(entity.get(field))]


def _compare_entity_fields(expected: dict, predicted: dict, fields: list[str]) -> tuple[int, int, int]:
    expected_fields = _filled_fields(expected, fields)
    predicted_fields = _filled_fields(predicted, fields)
    tp = sum(
        1
        for field in expected_fields
        if field in predicted_fields and _values_match(field, expected.get(field), predicted.get(field))
    )
    fp = len(predicted_fields) - tp
    fn = len(expected_fields) - tp
    return tp, fp, fn


def _score_pair(expected: dict, predicted: dict, fields: list[str]) -> int:
    tp, _, _ = _compare_entity_fields(expected, predicted, fields)
    return tp


def _compare_entity_list(expected_items: list[dict], predicted_items: list[dict], fields: list[str]) -> tuple[int, int, int]:
    remaining_predicted = list(predicted_items)
    tp = fp = fn = 0

    for expected in expected_items:
        if not remaining_predicted:
            expected_fields = _filled_fields(expected, fields)
            fn += len(expected_fields)
            continue

        best_index = max(
            range(len(remaining_predicted)),
            key=lambda index: _score_pair(expected, remaining_predicted[index], fields),
        )
        predicted = remaining_predicted.pop(best_index)
        pair_tp, pair_fp, pair_fn = _compare_entity_fields(expected, predicted, fields)
        tp += pair_tp
        fp += pair_fp
        fn += pair_fn

    for predicted in remaining_predicted:
        fp += len(_filled_fields(predicted, fields))

    return tp, fp, fn


def _prf(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision_value = 1.0 if tp == 0 and fp == 0 else tp / (tp + fp)
    recall_value = 1.0 if tp == 0 and fn == 0 else tp / (tp + fn)
    f1 = 0.0 if precision_value + recall_value == 0 else 2 * precision_value * recall_value / (precision_value + recall_value)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision_value,
        "recall": recall_value,
        "f1": f1,
    }


def compare_entities(expected: dict, predicted: dict) -> dict[str, dict[str, float | int]]:
    rows = {}
    total_tp = total_fp = total_fn = 0

    for entity_type, fields in ENTITY_FIELDS.items():
        if entity_type == "patient":
            tp, fp, fn = _compare_entity_fields(
                expected.get("patient", {}) or {},
                predicted.get("patient", {}) or {},
                fields,
            )
        else:
            tp, fp, fn = _compare_entity_list(
                expected.get(entity_type, []) or [],
                predicted.get(entity_type, []) or [],
                fields,
            )

        rows[entity_type] = _prf(tp, fp, fn)
        total_tp += tp
        total_fp += fp
        total_fn += fn

    rows["overall"] = _prf(total_tp, total_fp, total_fn)
    return rows


def flatten_metrics(metrics: dict[str, dict[str, float | int]]) -> dict[str, float | int]:
    flat = {}
    for entity_type, values in metrics.items():
        for metric_name, value in values.items():
            flat[f"{entity_type}_{metric_name}"] = value
    return flat
