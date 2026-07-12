from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "backend/src"
DEFAULT_INPUT = REPO_ROOT / "backend/eval/data/ner/ner_eval_samples.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "backend/eval/results/sanity_eval_results.csv"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            row.setdefault("sample_id", line_number)
            rows.append(row)
    return rows


def _format_dimension(entity: dict[str, Any]) -> str:
    unit = entity.get("unit") or "cm"
    dimension_keys = ["dim_x", "dim_y", "dim_z"]
    values = [
        str(entity[key]).rstrip("0").rstrip(".")
        for key in dimension_keys
        if entity.get(key) is not None
    ]

    if values:
        return f" o wymiarach {' x '.join(values)} {unit}"

    if entity.get("length") is not None:
        return f" o długości {entity['length']} {unit}"

    if entity.get("diameter") is not None:
        return f" o średnicy {entity['diameter']} {unit}"

    return ""


def _build_description(expected_entities: dict[str, Any]) -> str:
    parts = []

    for component in expected_entities.get("components", []) or []:
        name = component.get("name") or "komponent"
        parts.append(f"{name}{_format_dimension(component)}")

    for lesion in expected_entities.get("lesions", []) or []:
        lesion_type = lesion.get("type") or "zmiana"
        structure = lesion.get("structure")
        features = lesion.get("features") or []

        fragment = lesion_type
        if structure:
            fragment = f"{structure} {fragment}"
        fragment += _format_dimension(lesion)
        if features:
            fragment += f" z cechami: {', '.join(map(str, features))}"
        parts.append(fragment)

    for fluid_sample in expected_entities.get("fluid_samples", []) or []:
        material_type = fluid_sample.get("material_type") or "materiał płynny"
        source = fluid_sample.get("source")
        volume = fluid_sample.get("volume_ml")
        clarity = fluid_sample.get("clarity")

        fragment = str(material_type)
        if source:
            fragment += f" {source}"
        if volume is not None:
            fragment += f", {volume} ml"
        if clarity:
            fragment += f", {clarity}"
        parts.append(fragment)

    return ". ".join(parts)


def _infer_organ(expected_entities: dict[str, Any]) -> str:
    components = expected_entities.get("components", []) or []
    if components:
        return str(components[0].get("organ") or components[0].get("name") or "")

    lesions = expected_entities.get("lesions", []) or []
    if lesions:
        return str(lesions[0].get("organ") or lesions[0].get("location") or "")

    fluid_samples = expected_entities.get("fluid_samples", []) or []
    if fluid_samples:
        return str(fluid_samples[0].get("source") or fluid_samples[0].get("material_type") or "")

    return ""


def build_form_data(expected_entities: dict[str, Any]) -> dict[str, str]:
    patient = expected_entities.get("patient") or {}
    first_name = str(patient.get("first_name") or "").strip()
    last_name = str(patient.get("last_name") or "").strip()
    full_name = f"{first_name} {last_name}".strip()

    age = patient.get("age")

    return {
        "organ": _infer_organ(expected_entities),
        "name": full_name,
        "age": "" if age is None else str(age),
        "pesel": str(patient.get("pesel") or ""),
        "description": _build_description(expected_entities),
    }


def _issue_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "warning_count": sum(1 for issue in issues if issue.get("severity") == "warning"),
        "error_count": sum(1 for issue in issues if issue.get("severity") == "error"),
        "rules_issue_count": sum(1 for issue in issues if issue.get("source") == "rules"),
        "llm_issue_count": sum(1 for issue in issues if issue.get("source") == "llm_review"),
    }


def run_eval(args: argparse.Namespace) -> list[dict[str, Any]]:
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))

    from app_stt.services import data_sanity_check

    samples = _read_jsonl(args.input)
    if args.limit is not None:
        samples = samples[:args.limit]

    original_llm_review = data_sanity_check.check_with_llm
    if args.disable_llm_review:
        data_sanity_check.check_with_llm = lambda transcript, form_data, rule_issues: []

    rows = []
    try:
        for sample in samples:
            expected_entities = sample.get("expected_entities") or {}
            if isinstance(expected_entities, str):
                expected_entities = json.loads(expected_entities)

            transcript = str(sample.get("transcript") or "")
            form_data = build_form_data(expected_entities)
            result = data_sanity_check.run_data_sanity_check(transcript, form_data)
            issues = result.get("issues", [])
            issue_codes = sorted({str(issue.get("code", "")) for issue in issues if issue.get("code")})
            counts = _issue_counts(issues)

            rows.append({
                "sample_id": sample.get("sample_id", ""),
                "status": result.get("status", ""),
                "score": result.get("score", ""),
                "issue_count": len(issues),
                "issue_codes": "|".join(issue_codes),
                **counts,
                "description_length": result.get("metrics", {}).get("description_length", ""),
                "transcript_length": result.get("metrics", {}).get("transcript_length", ""),
                "manual_warning_sensible": "",
                "manual_false_positive": "",
                "manual_score_sensible": "",
                "manual_notes": "",
            })
    finally:
        data_sanity_check.check_with_llm = original_llm_review

    return rows


def write_results(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sample_id",
        "status",
        "score",
        "issue_count",
        "issue_codes",
        "warning_count",
        "error_count",
        "rules_issue_count",
        "llm_issue_count",
        "description_length",
        "transcript_length",
        "manual_warning_sensible",
        "manual_false_positive",
        "manual_score_sensible",
        "manual_notes",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run data sanity check evaluation on NER samples.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--disable-llm-review", action="store_true", default=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(f"Sanity eval input file does not exist: {args.input}")

    rows = run_eval(args)
    write_results(rows, args.output)

    print(f"Wrote sanity eval results: {args.output}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main()
