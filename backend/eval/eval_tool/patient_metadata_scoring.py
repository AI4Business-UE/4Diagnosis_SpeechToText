from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

PATIENT_METADATA_FIELDS = ("first_name", "last_name", "age", "pesel")


def aggregate_patient_metadata_scores(scores: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Average per-sample patient metadata scores and pool per-field correct/graded counts."""
    rows = list(scores)
    field_counts: dict[str, dict[str, int]] = {}
    for row in rows:
        for field, correct in row["fields"].items():
            counts = field_counts.setdefault(field, {"correct": 0, "graded": 0})
            counts["graded"] += 1
            counts["correct"] += int(correct)
    fields = {
        field: field_counts[field]
        for field in PATIENT_METADATA_FIELDS
        if field in field_counts
    }
    return {
        "samples": len(rows),
        "mean_score": sum(row["score"] for row in rows) / len(rows) if rows else None,
        "fields": fields,
    }


def score_patient_metadata(
    reference: Mapping[str, Any],
    extracted: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Grade the raw NER patient extraction against the patient metadata reference.

    Only fields set in the reference are graded; a reference without any set
    field yields no score. Each graded field counts 1 when extracted correctly
    and 0 otherwise, including when the extraction is missing entirely.
    """
    fields: dict[str, int] = {}
    for field in PATIENT_METADATA_FIELDS:
        expected = reference.get(field)
        if expected is None:
            continue
        actual = extracted.get(field) if extracted is not None else None
        fields[field] = int(_matches(field, expected, actual))
    if not fields:
        return None
    correct = sum(fields.values())
    return {"fields": fields, "score": correct / len(fields)}


def _matches(field: str, expected: Any, actual: Any) -> bool:
    if actual is None:
        return False
    if field == "age":
        return actual == expected
    if field == "pesel":
        return str(actual).strip() == expected
    if field in {"first_name", "last_name"}:
        return _normalize_name(actual) == _normalize_name(expected)
    return False


def _normalize_name(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip()).casefold()
