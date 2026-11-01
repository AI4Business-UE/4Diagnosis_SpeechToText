from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

_CATEGORIES = ("patient", "components", "lesions", "fluid_samples")
_PRIMARY_FIELDS = {
    "components": ("name",),
    "lesions": ("type", "organ"),
    "fluid_samples": ("material_type", "source"),
}
_MEASUREMENT_FIELDS = {"dim_x", "dim_y", "dim_z", "length", "diameter"}


def score_ner(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> dict[str, Any]:
    """Compare a sparse, reviewed NER reference with one pipeline extraction.

    Missing keys in a reference entity are unknown and are ignored. A key explicitly
    set to null means that attribute is known to be absent. Empty entity lists mean
    that the category is known to contain no entities.
    """
    _require_categories(expected, "reference")
    _require_categories(actual, "pipeline output")

    category_results: dict[str, Any] = {}
    exact_record_match = True

    patient_result, patient_exact = _score_patient(expected["patient"], actual["patient"])
    category_results["patient"] = patient_result
    exact_record_match &= patient_exact

    for category in _CATEGORIES[1:]:
        result, exact = _score_entity_category(category, expected[category], actual[category])
        category_results[category] = result
        exact_record_match &= exact

    return {
        "exact_record_match": bool(exact_record_match),
        "categories": category_results,
    }


def aggregate_ner_scores(scores: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Pool field and entity counts and retain an exact-record match rate."""
    rows = list(scores)
    category_counts: dict[str, dict[str, Any]] = {}
    all_fields: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for category in _CATEGORIES:
        entity_tp = entity_fp = entity_fn = 0
        field_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
        for row in rows:
            result = row["categories"][category]
            entity_counts = result["entity_counts"]
            entity_tp += entity_counts["true_positives"]
            entity_fp += entity_counts["false_positives"]
            entity_fn += entity_counts["false_negatives"]
            for field, counts in result["fields"].items():
                pooled = field_counts[field]
                pooled[0] += counts["true_positives"]
                pooled[1] += counts["false_positives"]
                pooled[2] += counts["false_negatives"]

        category_counts[category] = {
            "entity_counts": _counts(entity_tp, entity_fp, entity_fn),
            "fields": {
                field: _counts(*counts)
                for field, counts in sorted(field_counts.items())
            },
        }
        for field, counts in field_counts.items():
            _add_counts(all_fields[f"{category}.{field}"], tuple(counts))

    exact_matches = sum(bool(row["exact_record_match"]) for row in rows)
    return {
        "records": len(rows),
        "exact_record_matches": exact_matches,
        "exact_record_rate": exact_matches / len(rows) if rows else None,
        "fields": {
            field: _counts(*counts)
            for field, counts in sorted(all_fields.items())
        },
        "categories": category_counts,
    }


def _score_patient(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    fields: dict[str, Any] = {}
    exact = True
    for field, expected_value in expected.items():
        predicted_value = actual.get(field)
        counts = _field_counts(field, expected_value, predicted_value, expected, actual)
        fields[field] = _counts(*counts)
        exact &= _values_equal(field, expected_value, predicted_value, expected, actual)
    return {
        "entity_counts": _counts(
            int(
                any(value is not None for value in expected.values())
                and any(value is not None for value in actual.values())
            ),
            int(
                not any(value is not None for value in expected.values())
                and any(value is not None for value in actual.values())
            ),
            int(
                any(value is not None for value in expected.values())
                and not any(value is not None for value in actual.values())
            ),
        ),
        "fields": fields,
    }, bool(exact)


def _score_entity_category(
    category: str,
    expected: list[Mapping[str, Any]],
    actual: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], bool]:
    pairs, unmatched_expected, unmatched_actual = _match_entities(category, expected, actual)
    field_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    exact = len(expected) == len(actual) and not unmatched_expected and not unmatched_actual
    entity_tp = entity_fp = entity_fn = 0

    for expected_entity, actual_entity in pairs:
        entity_tp += 1
        entity_exact = True
        for field, expected_value in expected_entity.items():
            predicted_value = actual_entity.get(field)
            counts = _field_counts(field, expected_value, predicted_value, expected_entity, actual_entity)
            _add_counts(field_counts[field], counts)
            equal = _values_equal(field, expected_value, predicted_value, expected_entity, actual_entity)
            entity_exact &= equal
            if not equal:
                exact = False
        exact &= entity_exact

    for entity in unmatched_expected:
        entity_fn += 1
        for field, expected_value in entity.items():
            if expected_value is not None:
                _add_counts(field_counts[field], (0, 0, 1))
        exact = False

    for entity in unmatched_actual:
        entity_fp += 1
        for field, predicted_value in entity.items():
            if predicted_value is not None:
                _add_counts(field_counts[field], (0, 1, 0))
        exact = False

    return {
        "entity_counts": _counts(entity_tp, entity_fp, entity_fn),
        "fields": {
            field: _counts(*counts)
            for field, counts in sorted(field_counts.items())
        },
    }, bool(exact)


def _match_entities(
    category: str,
    expected: list[Mapping[str, Any]],
    actual: list[Mapping[str, Any]],
) -> tuple[list[tuple[Mapping[str, Any], Mapping[str, Any]]], list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    candidates: list[tuple[int, int, int]] = []
    for expected_index, expected_entity in enumerate(expected):
        for actual_index, actual_entity in enumerate(actual):
            score = sum(
                _values_equal(field, expected_value, actual_entity.get(field), expected_entity, actual_entity)
                for field, expected_value in expected_entity.items()
            )
            score += 2 * sum(
                1
                for field in _PRIMARY_FIELDS.get(category, ())
                if field in expected_entity
                and _values_equal(
                    field,
                    expected_entity[field],
                    actual_entity.get(field),
                    expected_entity,
                    actual_entity,
                )
            )
            if score:
                candidates.append((score, expected_index, actual_index))

    matched_expected: set[int] = set()
    matched_actual: set[int] = set()
    pairs: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for _, expected_index, actual_index in sorted(candidates, reverse=True):
        if expected_index in matched_expected or actual_index in matched_actual:
            continue
        matched_expected.add(expected_index)
        matched_actual.add(actual_index)
        pairs.append((expected[expected_index], actual[actual_index]))

    return (
        pairs,
        [entity for index, entity in enumerate(expected) if index not in matched_expected],
        [entity for index, entity in enumerate(actual) if index not in matched_actual],
    )


def _field_counts(
    field: str,
    expected: Any,
    actual: Any,
    expected_entity: Mapping[str, Any],
    actual_entity: Mapping[str, Any],
) -> tuple[int, int, int]:
    if expected is None:
        return (0, int(actual is not None), 0)
    if actual is None:
        return (0, 0, 1)
    return (1, 0, 0) if _values_equal(field, expected, actual, expected_entity, actual_entity) else (0, 1, 1)


def _values_equal(field: str, expected: Any, actual: Any, expected_entity: Mapping[str, Any], actual_entity: Mapping[str, Any]) -> bool:
    return _normalize(field, expected, expected_entity) == _normalize(field, actual, actual_entity)


def _normalize(field: str, value: Any, entity: Mapping[str, Any]) -> Any:
    if value is None:
        return None
    if field in _MEASUREMENT_FIELDS and isinstance(value, (int, float)):
        unit = entity.get("unit")
        normalized = float(value) * 10 if unit == "cm" else float(value)
        return round(normalized, 6)
    if field == "unit" and value in {"cm", "mm"}:
        return "metric_length"
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value.strip().lower())
    if isinstance(value, list):
        return tuple(sorted(_normalize("", item, entity) for item in value))
    return value


def _counts(true_positives: int, false_positives: int, false_negatives: int) -> dict[str, int | float]:
    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives
    precision = true_positives / precision_denominator if precision_denominator else 1.0
    recall = true_positives / recall_denominator if recall_denominator else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _add_counts(target: list[int], counts: tuple[int, int, int]) -> None:
    for index, count in enumerate(counts):
        target[index] += count


def _require_categories(value: Mapping[str, Any], label: str) -> None:
    missing = set(_CATEGORIES) - value.keys()
    if missing:
        raise ValueError(f"Brak kategorii NER w {label}: {', '.join(sorted(missing))}")
