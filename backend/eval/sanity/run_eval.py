from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "backend/src"
DEFAULT_INPUT = REPO_ROOT / "backend/eval/data/ner/ner_eval_samples.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "backend/eval/results/sanity_eval_results.csv"
DEFAULT_PREPROCESSED_DIR = REPO_ROOT / "backend/eval/results/preprocessed_audio/sanity"
MODES = ["rules", "rules_and_llm", "llm_only"]


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


def _normalize_baseline_entities(ner_json: dict[str, Any]) -> dict[str, Any]:
    patient = ner_json.get("Patient") or ner_json.get("patient") or {}
    components = ner_json.get("Components") or ner_json.get("components") or {}
    lesions = ner_json.get("Lesions") or ner_json.get("lesions") or {}
    fluid_samples = ner_json.get("Fluid sample") or ner_json.get("fluid_samples") or {}

    return {
        "patient": patient if isinstance(patient, dict) else {},
        "components": components.get("components", []) if isinstance(components, dict) else components or [],
        "lesions": lesions.get("lesions", []) if isinstance(lesions, dict) else lesions or [],
        "fluid_samples": (
            fluid_samples.get("fluid_samples", [])
            if isinstance(fluid_samples, dict)
            else fluid_samples or []
        ),
    }


def _read_baseline_csv(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)
        for line_number, row in enumerate(reader, start=1):
            raw_ner_json = row.get("ner_json") or ""
            if not raw_ner_json.strip():
                continue

            try:
                expected_entities = _normalize_baseline_entities(json.loads(raw_ner_json))
            except json.JSONDecodeError:
                continue

            model = row.get("model") or row.get("\ufeffmodel") or ""
            audio_file = row.get("plik") or ""
            rows.append({
                "sample_id": f"{model}:{audio_file}" if model or audio_file else line_number,
                "transcript": row.get("transkrypcja") or "",
                "expected_entities": expected_entities,
                "source_model": model,
                "audio_file": audio_file,
                "input_wer": row.get("WER") or "",
            })
    return rows


def _read_audio_manifest(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)
        for line_number, row in enumerate(reader, start=1):
            audio_path = row.get("audio_path") or ""
            audio_exists = str(row.get("audio_exists", "true")).lower() in {"true", "1", "yes"}
            if not audio_path or not audio_exists:
                continue

            rows.append({
                "sample_id": row.get("sample_id") or line_number,
                "audio_file": row.get("audio_file") or Path(audio_path).name,
                "audio_path": audio_path,
                "reference": row.get("ref_transcript") or "",
            })
    return rows


def load_samples(path: Path, input_format: str) -> list[dict[str, Any]]:
    if input_format == "jsonl":
        return _read_jsonl(path)
    if input_format == "baseline_csv":
        return _read_baseline_csv(path)
    if input_format == "audio_manifest":
        return _read_audio_manifest(path)

    if path.suffix.lower() == ".jsonl":
        return _read_jsonl(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as input_file:
            header = next(csv.reader(input_file), [])
        if "audio_path" in header:
            return _read_audio_manifest(path)
        return _read_baseline_csv(path)

    raise ValueError(f"Cannot infer sanity eval input format from: {path}")


def _format_number(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format_dimension(entity: dict[str, Any]) -> str:
    unit = entity.get("unit") or "cm"
    dimension_keys = ["dim_x", "dim_y", "dim_z"]
    values = [
        _format_number(entity[key])
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


def _load_pipeline_classes():
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))

    from app_stt.pipeline.config import PipelineConfig
    from app_stt.pipeline.pipeline import Pipeline
    return PipelineConfig, Pipeline


def _build_pipeline_config(model: str, preprocessing: str, ner_strategy: str, llm_model: str):
    PipelineConfig, _ = _load_pipeline_classes()
    config = PipelineConfig(
        whisper_model=model,
        ner_strategy=ner_strategy,
        llm_model=llm_model,
        preprocessing_output_dir=str(DEFAULT_PREPROCESSED_DIR / preprocessing),
    )

    if preprocessing == "baseline":
        return config
    if preprocessing == "volume_norm":
        config.use_volume_normalization = True
        config.use_bandpass_filter = False
        config.use_noise_reduction = False
        config.use_vad = False
        return config
    if preprocessing == "vad":
        config.use_vad = True
        return config
    if preprocessing == "noise_reduction":
        config.use_noise_reduction = True
        return config
    if preprocessing == "bandpass":
        config.use_bandpass_filter = True
        return config

    raise ValueError(f"Unknown preprocessing config: {preprocessing}")


def _issue_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "warning_count": sum(1 for issue in issues if issue.get("severity") == "warning"),
        "error_count": sum(1 for issue in issues if issue.get("severity") == "error"),
        "rules_issue_count": sum(1 for issue in issues if issue.get("source") == "rules"),
        "llm_issue_count": sum(1 for issue in issues if issue.get("source") == "llm_review"),
    }


def _run_rules_only(data_sanity_check, transcript: str, form_data: dict[str, str]) -> dict[str, Any]:
    original_llm_review = data_sanity_check.check_with_llm
    data_sanity_check.check_with_llm = lambda transcript, form_data, rule_issues: {
        "ran": False,
        "issues": [],
        "reason": "disabled",
    }
    try:
        return data_sanity_check.run_data_sanity_check(transcript, form_data)
    finally:
        data_sanity_check.check_with_llm = original_llm_review


def _run_rules_and_llm(data_sanity_check, transcript: str, form_data: dict[str, str]) -> dict[str, Any]:
    return data_sanity_check.run_data_sanity_check(transcript, form_data)


def _run_llm_only(data_sanity_check, transcript: str, form_data: dict[str, str]) -> dict[str, Any]:
    rule_result = _run_rules_only(data_sanity_check, transcript, form_data)
    rule_issues = rule_result.get("issues", [])
    llm = data_sanity_check.check_with_llm(transcript, form_data, rule_issues)
    issues = llm["issues"]

    return {
        "status": data_sanity_check.derive_status(issues),
        "score": data_sanity_check.calculate_score(issues),
        "issues": issues,
        "llm_review": {
            "ran": llm["ran"],
            "reason": llm["reason"],
            "issue_count": len(issues),
        },
        "metrics": {
            "transcript_length": len(transcript or ""),
            "description_length": len(str(form_data.get("description", "") or "")),
        },
    }


def _run_mode(data_sanity_check, mode: str, transcript: str, form_data: dict[str, str]) -> dict[str, Any]:
    if mode == "rules":
        return _run_rules_only(data_sanity_check, transcript, form_data)
    if mode == "rules_and_llm":
        return _run_rules_and_llm(data_sanity_check, transcript, form_data)
    if mode == "llm_only":
        return _run_llm_only(data_sanity_check, transcript, form_data)

    raise ValueError(f"Unknown sanity eval mode: {mode}")


def _filter_synthetic_patient_issues(
    issues: list[dict[str, Any]],
    sample: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    """W rekonstrukcji z gold-encji brak pacjenta w gold nie jest problemem jakości —
    to artefakt tego, że próbka NER nie miała danych pacjenta. Odfiltrowujemy takie
    braki name/age/pesel, żeby nie zawyżały issue_count. Zostają braki organ/description."""
    if not sample.get("synthetic") or sample.get("gold_has_patient") is not False:
        return issues, 0

    kept = []
    filtered = 0
    for issue in issues:
        if issue.get("code") == "missing_required_field" and issue.get("field") in {"name", "age", "pesel"}:
            filtered += 1
            continue
        kept.append(issue)
    return kept, filtered


def _build_result_row(
    data_sanity_check,
    sample_id: str,
    mode: str,
    result: dict[str, Any],
    sample: dict[str, Any],
) -> dict[str, Any]:
    issues, filtered_synthetic_issues = _filter_synthetic_patient_issues(
        result.get("issues", []), sample
    )

    # Po odfiltrowaniu artefaktów status/score liczymy ponownie, żeby wiersz był spójny.
    if filtered_synthetic_issues:
        status = data_sanity_check.derive_status(issues)
        score = data_sanity_check.calculate_score(issues)
    else:
        status = result.get("status", "")
        score = result.get("score", "")

    issue_codes = sorted({str(issue.get("code", "")) for issue in issues if issue.get("code")})
    issue_fields = sorted({str(issue.get("field", "")) for issue in issues if issue.get("field")})
    missing_fields = sorted({
        str(issue.get("field", ""))
        for issue in issues
        if issue.get("code") == "missing_required_field" and issue.get("field")
    })
    counts = _issue_counts(issues)
    llm_review = result.get("llm_review", {})

    return {
        "sample_id": sample_id,
        "source_model": sample.get("source_model", ""),
        "audio_file": sample.get("audio_file", ""),
        "input_wer": sample.get("input_wer", ""),
        "pipeline_model": sample.get("pipeline_model", ""),
        "preprocessing": sample.get("preprocessing", ""),
        "ner_strategy": sample.get("ner_strategy", ""),
        "pipeline_status": sample.get("pipeline_status", ""),
        "pipeline_error": sample.get("pipeline_error", ""),
        "pipeline_duration_seconds": sample.get("pipeline_duration_seconds", ""),
        "mode": mode,
        "status": status,
        "score": score,
        "issue_count": len(issues),
        "issue_codes": "|".join(issue_codes),
        "issue_fields": "|".join(issue_fields),
        "missing_fields": "|".join(missing_fields),
        **counts,
        "llm_ran": llm_review.get("ran", ""),
        "llm_reason": llm_review.get("reason", ""),
        "gold_has_patient": sample.get("gold_has_patient", ""),
        "filtered_synthetic_issues": filtered_synthetic_issues,
        "description_length": result.get("metrics", {}).get("description_length", ""),
        "transcript_length": result.get("metrics", {}).get("transcript_length", ""),
        "manual_warning_sensible": "",
        "manual_false_positive": "",
        "manual_score_sensible": "",
        "manual_notes": "",
    }


def _run_sanity_modes(
    data_sanity_check,
    sample: dict[str, Any],
    transcript: str,
    form_data: dict[str, str],
    modes: list[str],
) -> list[dict[str, Any]]:
    rows = []
    sample_id = str(sample.get("sample_id", ""))

    for mode in modes:
        result = _run_mode(data_sanity_check, mode, transcript, form_data)
        rows.append(_build_result_row(data_sanity_check, sample_id, mode, result, sample))

    return rows


def _run_audio_eval(args: argparse.Namespace, data_sanity_check, samples: list[dict[str, Any]], modes: list[str]) -> list[dict[str, Any]]:
    _, Pipeline = _load_pipeline_classes()
    rows = []

    for model in args.models:
        for preprocessing in args.preprocessing:
            for ner_strategy in args.ner_strategies:
                config = _build_pipeline_config(model, preprocessing, ner_strategy, args.llm_model)
                pipeline = Pipeline(config)

                for sample in samples:
                    eval_sample = {
                        **sample,
                        "pipeline_model": model,
                        "preprocessing": preprocessing,
                        "ner_strategy": ner_strategy,
                        "pipeline_status": "ok",
                        "pipeline_error": "",
                        # Realny fill z pipeline'u — brak pacjenta nie jest tu artefaktem.
                        "synthetic": False,
                        "gold_has_patient": "",
                    }

                    start = time.perf_counter()
                    try:
                        pipeline_result = pipeline.run(str(sample["audio_path"]))
                        duration = time.perf_counter() - start
                        transcript = str(pipeline_result.get("transcript") or "")
                        entities = pipeline_result.get("entities") or {}
                        form_data = build_form_data(entities)
                        eval_sample["pipeline_duration_seconds"] = round(duration, 4)
                    except Exception as exc:
                        duration = time.perf_counter() - start
                        transcript = ""
                        form_data = build_form_data({})
                        eval_sample.update({
                            "pipeline_status": "error",
                            "pipeline_error": str(exc),
                            "pipeline_duration_seconds": round(duration, 4),
                        })

                    rows.extend(_run_sanity_modes(data_sanity_check, eval_sample, transcript, form_data, modes))

    return rows


def run_eval(args: argparse.Namespace) -> list[dict[str, Any]]:
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))

    from app_stt.services import data_sanity_check

    samples = load_samples(args.input, args.input_format)
    if args.limit is not None:
        samples = samples[:args.limit]
    if not samples:
        return []

    modes = MODES if args.mode == "all" else [args.mode]

    if args.input_format == "audio_manifest" or (
        args.input_format == "auto" and samples and "audio_path" in samples[0]
    ):
        return _run_audio_eval(args, data_sanity_check, samples, modes)

    rows = []
    for sample in samples:
        expected_entities = sample.get("expected_entities") or {}
        if isinstance(expected_entities, str):
            expected_entities = json.loads(expected_entities)

        # Formularz jest tu syntetyczną rekonstrukcją z gold-encji, nie realnym fillem LLM.
        sample = {
            **sample,
            "synthetic": True,
            "gold_has_patient": bool(expected_entities.get("patient")),
        }

        transcript = str(sample.get("transcript") or "")
        form_data = build_form_data(expected_entities)
        rows.extend(_run_sanity_modes(data_sanity_check, sample, transcript, form_data, modes))

    return rows


def write_results(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sample_id",
        "source_model",
        "audio_file",
        "input_wer",
        "pipeline_model",
        "preprocessing",
        "ner_strategy",
        "pipeline_status",
        "pipeline_error",
        "pipeline_duration_seconds",
        "mode",
        "status",
        "score",
        "issue_count",
        "issue_codes",
        "issue_fields",
        "missing_fields",
        "warning_count",
        "error_count",
        "rules_issue_count",
        "llm_issue_count",
        "llm_ran",
        "llm_reason",
        "gold_has_patient",
        "filtered_synthetic_issues",
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
    parser.add_argument(
        "--input-format",
        choices=["auto", "jsonl", "baseline_csv", "audio_manifest"],
        default="auto",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--models", nargs="+", default=["whisper-small"])
    parser.add_argument("--preprocessing", nargs="+", default=["baseline"])
    parser.add_argument("--ner-strategies", nargs="+", default=["chained"])
    parser.add_argument("--llm-model", default="openai/gpt-4o")
    parser.add_argument(
        "--mode",
        choices=[*MODES, "all"],
        default="rules",
        help="rules = heuristics only, rules_and_llm = production flow, llm_only = LLM review with production rule issue context.",
    )
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
