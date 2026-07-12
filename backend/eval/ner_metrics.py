from __future__ import annotations

import json
import math
import re
from typing import Any


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


def _normalize_text(value: Any) -> str:
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
        expected_set = {_normalize_text(item) for item in expected or [] if not _is_empty(item)}
        predicted_set = {_normalize_text(item) for item in predicted or [] if not _is_empty(item)}
        return expected_set == predicted_set

    if field in NUMERIC_FIELDS:
        expected_number = _normalize_number(expected)
        predicted_number = _normalize_number(predicted)
        if expected_number is None or predicted_number is None:
            return expected_number == predicted_number
        return math.isclose(expected_number, predicted_number, rel_tol=0.0, abs_tol=0.001)

    return _normalize_text(expected) == _normalize_text(predicted)


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
    precision = 1.0 if tp == 0 and fp == 0 else tp / (tp + fp)
    recall = 1.0 if tp == 0 and fn == 0 else tp / (tp + fn)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
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


def _self_check() -> None:
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


if __name__ == "__main__":
    _self_check()
    print("NER metrics self-check passed")
