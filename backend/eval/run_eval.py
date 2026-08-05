"""Jeden eval dla całego pipeline'u 4Diagnosis: audio → STT → NER → RAG/answerer → sanity check.

Które etapy odpalić i z jakimi parametrami wybierasz w config.yaml (obok tego pliku).
Uruchomienie:

    backend/venv/bin/python backend/eval/run_eval.py
    backend/venv/bin/python backend/eval/run_eval.py --config backend/eval/config.yaml

Etapy (config `stages`):
    end_to_end – domyślny eval całego przepływu: audio → STT → NER → RAG/answerer → formularz → sanity check
                 (metryki STT + NER, jeśli gold ma referencje, + status/score/issues)
    stt    – diagnostyka samej transkrypcji: audio → preprocessing → STT (metryki STT)
    ner    – diagnostyka samego NER: transkrypt gold → NER, bez audio (metryki NER)

Uwaga: `stages: [stt, ner, end_to_end]` uruchamia STT/NER także osobno, więc jest droższe
i częściowo redundantne. Używaj tego wariantu tylko do pełnej diagnostyki.

Wyniki lądują w results/ jako stt_results.csv / ner_results.csv / end_to_end_results.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

EVAL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EVAL_ROOT.parents[1]
SRC_ROOT = REPO_ROOT / "backend/src"
DEFAULT_CONFIG = EVAL_ROOT / "config.yaml"

sys.path.insert(0, str(EVAL_ROOT))
from metrics import compare_entities, compute_stt_metrics, flatten_metrics, parse_entities  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════════
# Config + ścieżki
# ══════════════════════════════════════════════════════════════════════════════

def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as config_file:
        return yaml.safe_load(config_file) or {}


def resolve_path(value: str | Path) -> Path:
    """Ścieżki z configu są względne do backend/eval/."""
    path = Path(value)
    return path if path.is_absolute() else (EVAL_ROOT / path)


def write_rows(rows: list[dict[str, Any]], path: Path, leading: tuple[str, ...] = ()) -> None:
    if not rows:
        print(f"  (brak wierszy — nic nie zapisano do {path.name})")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    all_keys = {key for row in rows for key in row}
    ordered = [key for key in leading if key in all_keys] + sorted(all_keys - set(leading))
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=ordered)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  zapisano {len(rows)} wierszy → {path}")


# ══════════════════════════════════════════════════════════════════════════════
# Ładowanie komponentów aplikacji (app_stt)
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_src_on_path() -> None:
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))


def load_pipeline_classes():
    _ensure_src_on_path()
    from app_stt.pipeline.config import PipelineConfig
    from app_stt.pipeline.pipeline import Pipeline
    return PipelineConfig, Pipeline


def load_stt_components():
    _ensure_src_on_path()
    from app_stt.pipeline.stages.preprocessing import AudioPreprocessor
    from app_stt.pipeline.stages.stt.whisper_local import WhisperLocal
    return AudioPreprocessor, WhisperLocal


def load_ner_strategy(strategy_name: str, model: str):
    _ensure_src_on_path()
    if strategy_name == "chained":
        from app_stt.pipeline.stages.ner.chained import ChainedNERStrategy
        return ChainedNERStrategy(model=model)
    if strategy_name == "split":
        from app_stt.pipeline.stages.ner.split import SplitNERStrategy
        return SplitNERStrategy(model=model)
    raise ValueError(f"Nieznana strategia NER: {strategy_name}")


def load_data_sanity_check():
    _ensure_src_on_path()
    from app_stt.services import data_sanity_check
    return data_sanity_check


def build_pipeline_config(
    model: str,
    preprocessing: str,
    ner_strategy: str,
    llm_model: str,
    preprocessing_output_dir: Path,
    sanity_mode: str = "rules",
    enable_sanity_check: bool = True,
):
    PipelineConfig, _ = load_pipeline_classes()
    config = PipelineConfig(
        stt_model="whisper_local",
        whisper_model=model,
        ner_strategy=ner_strategy,
        ner_llm_model=llm_model,
        answerer_llm_model=llm_model,
        sanity_mode=sanity_mode,
        enable_sanity_check=enable_sanity_check,
        preprocessing_output_dir=str(preprocessing_output_dir),
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

    raise ValueError(f"Nieznana konfiguracja preprocessingu: {preprocessing}")


# ══════════════════════════════════════════════════════════════════════════════
# Manifest (audio + tekst referencyjny) — budowany z metadata + audio_dir
# ══════════════════════════════════════════════════════════════════════════════

def build_manifest(metadata_path: Path, audio_dir: Path) -> pd.DataFrame:
    metadata = pd.read_excel(metadata_path)
    rows = []
    for _, row in metadata.iterrows():
        file_name = row.get("nazwa pliku")
        reference = row.get("tekst referencyjny")
        if pd.isna(file_name) or pd.isna(reference):
            continue
        audio_path = audio_dir / str(file_name)
        rows.append({
            "sample_id": row.get("id", ""),
            "audio_file": str(file_name),
            "audio_path": str(audio_path),
            "ref_transcript": str(reference),
            "source": "local_stt_dataset",
            "speaker": row.get("twórca", ""),
            "format": row.get("format", ""),
            "audio_exists": audio_path.exists(),
        })
    return pd.DataFrame(rows)


def ensure_manifest(paths: dict[str, Any]) -> Path:
    manifest = resolve_path(paths["manifest"])
    if manifest.exists():
        return manifest

    metadata = resolve_path(paths["metadata"])
    audio_dir = resolve_path(paths["audio_dir"])
    if not metadata.exists():
        raise SystemExit(
            f"Brak manifestu ({manifest}) i metadanych do jego zbudowania ({metadata}). "
            "Skopiuj samples_metadata.xlsx oraz audio do data/."
        )

    manifest_df = build_manifest(metadata, audio_dir)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest_df.to_csv(manifest, index=False)
    found = int(manifest_df["audio_exists"].sum()) if len(manifest_df) else 0
    print(f"  zbudowano manifest: {manifest} ({len(manifest_df)} próbek, audio: {found})")
    return manifest


# ══════════════════════════════════════════════════════════════════════════════
# Etap STT
# ══════════════════════════════════════════════════════════════════════════════

def _transcribe_one(preprocessor, stt_model, audio_path: str) -> tuple[str, dict, float, float]:
    preprocessing_start = time.perf_counter()
    preprocessing_meta = preprocessor.process(audio_path)
    preprocessing_duration = time.perf_counter() - preprocessing_start

    stt_start = time.perf_counter()
    stt_result = stt_model.transcribe(preprocessing_meta["output_path"])
    stt_duration = time.perf_counter() - stt_start

    transcript = stt_result.get("text", "") if isinstance(stt_result, dict) else str(stt_result)
    return transcript, preprocessing_meta, preprocessing_duration, stt_duration


def run_stt(config: dict[str, Any], output_dir: Path) -> None:
    print("[stt] audio → preprocessing → STT")
    manifest_path = ensure_manifest(config["paths"])
    manifest = pd.read_csv(manifest_path)
    manifest = manifest[manifest["audio_exists"].astype(bool)]
    if config.get("limit") is not None:
        manifest = manifest.head(config["limit"])

    AudioPreprocessor, WhisperLocal = load_stt_components()
    preprocessed_dir = output_dir / "preprocessed_audio" / "stt"
    rows = []

    for model in config["models"]:
        model_config = build_pipeline_config(model, "baseline", config["ner_strategies"][0], config["llm_model"], preprocessed_dir)
        stt_model = WhisperLocal(model_id=model_config.whisper_hf_id)

        for preprocessing in config["preprocessing"]:
            pipeline_config = build_pipeline_config(
                model, preprocessing, config["ner_strategies"][0], config["llm_model"],
                preprocessed_dir / preprocessing,
            )
            preprocessor = AudioPreprocessor(pipeline_config)

            for _, sample in manifest.iterrows():
                row = {
                    "sample_id": sample.get("sample_id", ""),
                    "audio_file": sample["audio_file"],
                    "model": model,
                    "preprocessing": preprocessing,
                    "reference": sample["ref_transcript"],
                    "transcript": "",
                    "status": "ok",
                    "error": "",
                }
                try:
                    transcript, meta, preprocessing_duration, stt_duration = _transcribe_one(
                        preprocessor, stt_model, sample["audio_path"],
                    )
                    metrics = compute_stt_metrics(sample["ref_transcript"], transcript)
                    audio_duration = float(meta.get("original_duration_seconds") or 0)
                    duration = preprocessing_duration + stt_duration
                    row.update({
                        "transcript": transcript,
                        **metrics,
                        "preprocessing_duration_seconds": round(preprocessing_duration, 4),
                        "stt_duration_seconds": round(stt_duration, 4),
                        "duration_seconds": round(duration, 4),
                        "audio_duration_seconds": audio_duration,
                        "real_time_factor": round(duration / audio_duration, 4) if audio_duration else None,
                    })
                except Exception as exc:  # noqa: BLE001
                    row.update({"status": "error", "error": str(exc)})
                rows.append(row)

    write_rows(rows, output_dir / "stt_results.csv", leading=("sample_id", "audio_file", "model", "preprocessing", "status"))
    _summarize_stt(rows)


def _summarize_stt(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    frame = pd.DataFrame(rows)
    ok = frame[frame["status"] == "ok"]
    errors = len(frame) - len(ok)
    mean_wer = round(ok["wer"].mean(), 4) if "wer" in ok and len(ok) else None
    critical = int(ok["has_critical_error"].sum()) if "has_critical_error" in ok and len(ok) else 0
    print(f"  podsumowanie: {len(ok)} ok, {errors} błędów, mean WER={mean_wer}, próbki krytyczne={critical}")


# ══════════════════════════════════════════════════════════════════════════════
# Etap NER
# ══════════════════════════════════════════════════════════════════════════════

def _read_ner_gold(path: Path, limit: int | None) -> list[dict[str, Any]]:
    rows = []
    if path.suffix.lower() == ".jsonl":
        with path.open(encoding="utf-8") as input_file:
            for line_number, line in enumerate(input_file, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                row.setdefault("sample_id", line_number)
                rows.append(row)
    else:
        frame = pd.read_csv(path)
        rows = frame.to_dict("records")

    for row in rows:
        if "transcript" not in row or "expected_entities" not in row:
            raise ValueError("Gold NER musi mieć kolumny transcript + expected_entities")
    return rows[:limit] if limit is not None else rows


def run_ner(config: dict[str, Any], output_dir: Path) -> None:
    print("[ner] transkrypt → NER")
    samples = _read_ner_gold(resolve_path(config["paths"]["ner_gold"]), config.get("limit"))
    rows = []

    for strategy_name in config["ner_strategies"]:
        strategy = load_ner_strategy(strategy_name, config["llm_model"])

        for sample in samples:
            expected = parse_entities(sample["expected_entities"])
            transcript = str(sample["transcript"])
            row = {
                "sample_id": sample.get("sample_id", ""),
                "strategy": strategy_name,
                "model": config["llm_model"],
                "transcript": transcript,
                "expected_entities": json.dumps(expected, ensure_ascii=False, sort_keys=True),
                "predicted_entities": "",
                "status": "ok",
                "error": "",
            }
            start = time.perf_counter()
            try:
                predicted = strategy.extract(transcript).model_dump()
                row.update({
                    "predicted_entities": json.dumps(predicted, ensure_ascii=False, sort_keys=True),
                    "duration_seconds": round(time.perf_counter() - start, 4),
                    **flatten_metrics(compare_entities(expected, predicted)),
                })
            except Exception as exc:  # noqa: BLE001
                row.update({
                    "status": "error",
                    "error": str(exc),
                    "duration_seconds": round(time.perf_counter() - start, 4),
                })
            rows.append(row)

    write_rows(rows, output_dir / "ner_results.csv", leading=("sample_id", "strategy", "model", "status"))
    _summarize_ner(rows)


def _summarize_ner(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    frame = pd.DataFrame(rows)
    ok = frame[frame["status"] == "ok"]
    errors = len(frame) - len(ok)
    mean_f1 = round(ok["overall_f1"].mean(), 4) if "overall_f1" in ok and len(ok) else None
    print(f"  podsumowanie: {len(ok)} ok, {errors} błędów, mean overall_f1={mean_f1}")


# ══════════════════════════════════════════════════════════════════════════════
# Etap sanity — pełny pipeline audio → STT → NER → RAG/answerer → formularz → sanity check
# (oraz warianty offline: gotowy formularz / rekonstrukcja z gold-encji)
# ══════════════════════════════════════════════════════════════════════════════

def _format_number(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format_dimension(entity: dict[str, Any]) -> str:
    unit = entity.get("unit") or "cm"
    values = [_format_number(entity[key]) for key in ("dim_x", "dim_y", "dim_z") if entity.get(key) is not None]
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
    age = patient.get("age")
    return {
        "organ": _infer_organ(expected_entities),
        "name": f"{first_name} {last_name}".strip(),
        "age": "" if age is None else str(age),
        "pesel": str(patient.get("pesel") or ""),
        "description": _build_description(expected_entities),
    }


def _read_end_to_end_input(path: Path, limit: int | None) -> tuple[list[dict[str, Any]], str]:
    """Wykrywa format wejścia i zwraca (próbki, format).
    Format: 'audio' (audio_path), 'form' (form_data), 'entities' (expected_entities)."""
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
        records = frame.to_dict("records")
        for index, row in enumerate(records, start=1):
            row.setdefault("sample_id", index)
        if "audio_path" in frame.columns:
            samples = [row for row in records if str(row.get("audio_path") or "").strip()]
            return (samples[:limit] if limit is not None else samples), "audio"
        return (records[:limit] if limit is not None else records), "entities"

    # JSONL
    records = []
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            row["sample_id"] = row.get("form_id") or row.get("sample_id") or line_number
            records.append(row)
    if records and "form_data" in records[0]:
        fmt = "form"
    else:
        fmt = "entities"
    return (records[:limit] if limit is not None else records), fmt


def _issue_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "warning_count": sum(1 for issue in issues if issue.get("severity") == "warning"),
        "error_count": sum(1 for issue in issues if issue.get("severity") == "error"),
        "rules_issue_count": sum(1 for issue in issues if issue.get("source") == "rules"),
    }


def _trace_config(config: dict[str, Any]) -> dict[str, Any]:
    trace = config.get("trace") or {}
    if not isinstance(trace, dict):
        return {"enabled": False}
    return {
        "enabled": bool(trace.get("enabled")),
        "path": trace.get("path") or "results/full_app_trace.jsonl",
    }


def _trace_path(config: dict[str, Any]) -> Path | None:
    trace = _trace_config(config)
    if not trace["enabled"]:
        return None

    path = Path(trace["path"])
    return path if path.is_absolute() else (EVAL_ROOT / path)


def _present_form_fields(form_data: dict[str, Any]) -> list[str]:
    hidden_fields = {"name", "pesel"}
    return sorted(
        field
        for field, value in form_data.items()
        if field not in hidden_fields and str(value or "").strip()
    )


def _entity_counts(entities: dict[str, Any]) -> dict[str, int]:
    return {
        "components": len(entities.get("components") or []),
        "lesions": len(entities.get("lesions") or []),
        "fluid_samples": len(entities.get("fluid_samples") or []),
    }


def _template_count(templates: Any) -> int:
    if isinstance(templates, list):
        return len(templates)
    if isinstance(templates, dict):
        return len(templates)
    return 0


def _safe_trace_error(error: Any, sample: dict[str, Any], limit: int = 500) -> str:
    text = str(error or "")
    for key in ("audio_path", "audio_file"):
        value = str(sample.get(key) or "")
        if value:
            text = text.replace(value, Path(value).name)
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def _audio_file_label(sample: dict[str, Any]) -> str:
    value = sample.get("audio_file") or sample.get("audio_path") or ""
    return Path(str(value)).name if value else ""


def build_minimal_trace(
    sample: dict[str, Any],
    eval_sample: dict[str, Any],
    pipeline_result: dict[str, Any] | None,
    sanity_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    record = {
        "sample_id": str(sample.get("sample_id", "")),
        "audio_file": _audio_file_label(sample),
        "pipeline_model": eval_sample.get("pipeline_model", ""),
        "preprocessing": eval_sample.get("preprocessing", ""),
        "ner_strategy": eval_sample.get("ner_strategy", ""),
        "pipeline_status": eval_sample.get("pipeline_status", ""),
        "pipeline_duration_seconds": eval_sample.get("pipeline_duration_seconds", ""),
    }

    if eval_sample.get("pipeline_status") == "error":
        record["pipeline_error"] = _safe_trace_error(eval_sample.get("pipeline_error", ""), sample)
        record["stages"] = {"pipeline": {"status": "error"}}
        return record

    pipeline_result = pipeline_result or {}
    transcript = pipeline_result.get("transcript", "")
    corrected_transcript = pipeline_result.get("corrected_transcript", "")
    entities = pipeline_result.get("entities", {})
    form_data = pipeline_result.get("form_data", {})
    templates = pipeline_result.get("retrieved_templates", [])
    primary_sanity = sanity_rows[0] if sanity_rows else {}

    record["stages"] = {
        "stt": {"status": "ok", "transcript_length": len(transcript or "")},
        "ner": {"status": "ok", "entity_counts": _entity_counts(entities)},
        "rag": {"status": "ok", "template_count": _template_count(templates)},
        "answerer": {"status": "ok", "corrected_length": len(corrected_transcript or "")},
        "form_data": {"status": "ok", "present_fields": _present_form_fields(form_data)},
        "sanity": {
            "status": primary_sanity.get("status", ""),
            "score": primary_sanity.get("score", ""),
            "issue_codes": primary_sanity.get("issue_codes", "").split("|")
            if primary_sanity.get("issue_codes") else [],
        },
    }
    return record


def append_trace_record(record: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as trace_file:
        trace_file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _score_bucket(status: str, score: Any, issue_count: int) -> str:
    if status == "critical":
        return "critical"

    try:
        score_value = float(score)
    except (TypeError, ValueError):
        return ""

    if issue_count == 0 and score_value == 1.0:
        return "ok"
    if score_value < 0.6:
        return "critical"
    if score_value < 0.8:
        return "major"
    if score_value < 1.0:
        return "minor"
    return "ok"


def _parse_expected_issue_codes(value: Any) -> set[str]:
    if value is None or value == "":
        return set()
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return set()
        if value.startswith("["):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return {str(code).strip() for code in parsed if str(code).strip()}
            except json.JSONDecodeError:
                pass
        return {code.strip() for code in value.split("|") if code.strip()}
    if isinstance(value, (list, tuple, set)):
        return {str(code).strip() for code in value if str(code).strip()}
    return {str(value).strip()}


def _filter_synthetic_patient_issues(issues: list[dict[str, Any]], sample: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """W rekonstrukcji z gold-encji brak pacjenta nie jest problemem jakości — to artefakt
    tego, że próbka nie miała danych pacjenta. Odfiltrowujemy braki name/age/pesel."""
    if not sample.get("synthetic") or sample.get("gold_has_patient") is not False:
        return issues, 0
    kept, filtered = [], 0
    for issue in issues:
        if issue.get("code") == "missing_required_field" and issue.get("field") in {"name", "age", "pesel"}:
            filtered += 1
            continue
        kept.append(issue)
    return kept, filtered


def _build_sanity_row(data_sanity_check, result: dict[str, Any], sample: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    issues, filtered_synthetic_issues = _filter_synthetic_patient_issues(result.get("issues", []), sample)
    llm_review = result.get("llm_review", {})
    if filtered_synthetic_issues:
        status = data_sanity_check.derive_status(issues)
        score = data_sanity_check.calculate_score(issues)
    else:
        status = result.get("status", "")
        score = result.get("score", "")

    issue_codes = sorted({str(issue.get("code", "")) for issue in issues if issue.get("code")})
    issue_fields = sorted({str(issue.get("field", "")) for issue in issues if issue.get("field")})
    missing_fields = sorted({
        str(issue.get("field", "")) for issue in issues
        if issue.get("code") == "missing_required_field" and issue.get("field")
    })

    # Zgodność z gold: predicted = sanity coś zgłosił (status != ok). flag_match liczymy tylko gdy
    # gold ma bool expected_flag (fixture); dla audio bez etykiety zostaje puste.
    expected_flag = sample.get("expected_flag", "")
    predicted_flag = status != "ok"
    flag_match = (predicted_flag == expected_flag) if isinstance(expected_flag, bool) else ""
    bucket = _score_bucket(status, score, len(issues))
    expected_severity = sample.get("expected_severity", "")
    severity_match = bucket == expected_severity if expected_severity else ""
    expected_issue_codes = _parse_expected_issue_codes(sample.get("expected_issue_codes"))
    actual_issue_codes = set(issue_codes)
    missing_expected_issue_codes = sorted(expected_issue_codes - actual_issue_codes)
    unexpected_issue_codes = sorted(actual_issue_codes - expected_issue_codes)
    issue_code_match = expected_issue_codes.issubset(actual_issue_codes) if expected_issue_codes else ""

    row = {
        "sample_id": str(sample.get("sample_id", "")),
        "audio_file": sample.get("audio_file", ""),
        "pipeline_model": sample.get("pipeline_model", ""),
        "preprocessing": sample.get("preprocessing", ""),
        "ner_strategy": sample.get("ner_strategy", ""),
        "pipeline_status": sample.get("pipeline_status", ""),
        "pipeline_error": sample.get("pipeline_error", ""),
        "pipeline_duration_seconds": sample.get("pipeline_duration_seconds", ""),
        "sanity_mode": sample.get("sanity_mode", ""),
        "status": status,
        "score": score,
        "issue_count": len(issues),
        "issue_codes": "|".join(issue_codes),
        "issue_fields": "|".join(issue_fields),
        "missing_fields": "|".join(missing_fields),
        **_issue_counts(issues),
        "gold_has_patient": sample.get("gold_has_patient", ""),
        "filtered_synthetic_issues": filtered_synthetic_issues,
        "expected_flag": expected_flag,
        "predicted_flag": predicted_flag,
        "flag_match": flag_match,
        "expected_severity": expected_severity,
        "score_bucket": bucket,
        "severity_match": severity_match,
        "expected_issue_codes": "|".join(sorted(expected_issue_codes)),
        "issue_code_match": issue_code_match,
        "missing_expected_issue_codes": "|".join(missing_expected_issue_codes),
        "unexpected_issue_codes": "|".join(unexpected_issue_codes) if expected_issue_codes else "",
        "llm_ran": llm_review.get("ran", ""),
        "llm_reason": llm_review.get("reason", ""),
        "llm_issue_count": llm_review.get("issue_count", ""),
        "note": sample.get("note", ""),
        "description_length": result.get("metrics", {}).get("description_length", ""),
        "transcript_length": result.get("metrics", {}).get("transcript_length", ""),
        "manual_warning_sensible": "",
        "manual_false_positive": "",
        "manual_score_sensible": "",
        "manual_notes": "",
    }
    row.update(extra)
    return row


def _run_sanity(data_sanity_check, sample: dict[str, Any], transcript: str, form_data: dict[str, str], extra: dict[str, Any]) -> dict[str, Any]:
    result = data_sanity_check.run_data_sanity_check(
        transcript,
        form_data,
        mode=sample.get("sanity_mode", "rules"),
    )
    return _build_sanity_row(data_sanity_check, result, sample, extra)


def _sanity_modes(config: dict[str, Any]) -> list[str]:
    modes = config.get("sanity_modes") or ["rules"]
    if isinstance(modes, str):
        modes = [modes]
    return list(modes)


def _audio_extra_metrics(sample: dict[str, Any], transcript: str, entities: dict[str, Any]) -> dict[str, Any]:
    """Przy realnym audio dokładamy metryki STT (vs ref_transcript) i NER (vs expected_entities),
    jeśli gold je ma."""
    extra: dict[str, Any] = {}
    reference = sample.get("reference") or sample.get("ref_transcript") or ""
    if isinstance(reference, str) and reference.strip():
        extra.update({f"stt_{key}": value for key, value in compute_stt_metrics(reference, transcript).items()})

    expected_raw = sample.get("expected_entities")
    if isinstance(expected_raw, str) and expected_raw.strip() or isinstance(expected_raw, dict) and expected_raw:
        expected = parse_entities(expected_raw)
        extra.update({f"ner_{key}": value for key, value in flatten_metrics(compare_entities(expected, entities)).items()})
    return extra


def _run_sanity_audio(config: dict[str, Any], data_sanity_check, samples: list[dict[str, Any]], output_dir: Path) -> list[dict[str, Any]]:
    _PipelineConfig, Pipeline = load_pipeline_classes()
    preprocessed_dir = output_dir / "preprocessed_audio" / "sanity"
    sanity_modes = _sanity_modes(config)
    trace_path = _trace_path(config)
    rows = []

    for model in config["models"]:
        for preprocessing in config["preprocessing"]:
            for ner_strategy in config["ner_strategies"]:
                pipeline_config = build_pipeline_config(
                    model,
                    preprocessing,
                    ner_strategy,
                    config["llm_model"],
                    preprocessed_dir / preprocessing,
                    enable_sanity_check=False,
                )
                pipeline = Pipeline(pipeline_config)

                for sample in samples:
                    base_sample = {
                        **sample,
                        "pipeline_model": model,
                        "preprocessing": preprocessing,
                        "ner_strategy": ner_strategy,
                        "pipeline_status": "ok",
                        "pipeline_error": "",
                        "synthetic": False,
                        "gold_has_patient": "",
                    }
                    start = time.perf_counter()
                    try:
                        pipeline_result = pipeline.run(str(sample["audio_path"]))
                        transcript = pipeline_result.get("transcript", "")
                        corrected_transcript = pipeline_result.get("corrected_transcript", transcript)
                        entities = pipeline_result.get("entities", {})
                        form_data = pipeline_result.get("form_data", {})
                        base_sample["pipeline_duration_seconds"] = round(time.perf_counter() - start, 4)
                        extra = _audio_extra_metrics(sample, transcript, entities)
                        sanity_rows = []

                        for sanity_mode in sanity_modes:
                            sanity_row = _run_sanity(
                                data_sanity_check,
                                {**base_sample, "sanity_mode": sanity_mode},
                                corrected_transcript,
                                form_data,
                                extra,
                            )
                            rows.append(sanity_row)
                            sanity_rows.append(sanity_row)

                        if trace_path is not None:
                            append_trace_record(
                                build_minimal_trace(sample, base_sample, pipeline_result, sanity_rows),
                                trace_path,
                            )
                    except Exception as exc:  # noqa: BLE001
                        base_sample.update({
                            "pipeline_status": "error",
                            "pipeline_error": str(exc),
                            "pipeline_duration_seconds": round(time.perf_counter() - start, 4),
                        })
                        empty_result = {
                            "status": "",
                            "score": "",
                            "issues": [],
                            "metrics": {},
                            "llm_review": {},
                        }
                        for sanity_mode in sanity_modes:
                            rows.append(_build_sanity_row(
                                data_sanity_check,
                                empty_result,
                                {**base_sample, "sanity_mode": sanity_mode},
                                {},
                            ))
                        if trace_path is not None:
                            append_trace_record(
                                build_minimal_trace(sample, base_sample, None, []),
                                trace_path,
                            )
    return rows


def run_end_to_end(config: dict[str, Any], output_dir: Path) -> None:
    print("[end_to_end] audio → STT → NER → RAG/answerer → formularz → sanity check")
    data_sanity_check = load_data_sanity_check()

    input_path = config["paths"].get("end_to_end_input") or config["paths"].get("sanity_input")
    if not input_path:
        raise SystemExit("Brak paths.end_to_end_input w configu.")

    samples, fmt = _read_end_to_end_input(resolve_path(input_path), config.get("limit"))
    if not samples:
        write_rows([], output_dir / "end_to_end_results.csv")
        return

    sanity_modes = _sanity_modes(config)
    if fmt == "audio":
        rows = _run_sanity_audio(config, data_sanity_check, samples, output_dir)
    elif fmt == "form":
        rows = []
        for sample in samples:
            form_data = sample.get("form_data") or {}
            if isinstance(form_data, str):
                form_data = json.loads(form_data)
            # Uodpornienie na time-drift: dla ok-case (expected_flag False) licz wiek z PESEL-a,
            # żeby age_pesel_mismatch nie zależał od dzisiejszej daty. Bad-case zostają nietknięte.
            if sample.get("expected_flag") is False:
                pesel_age = data_sanity_check._age_from_pesel(form_data.get("pesel", ""))
                if pesel_age is not None:
                    form_data = {**form_data, "age": str(pesel_age)}
            sample = {**sample, "synthetic": False, "gold_has_patient": ""}
            for sanity_mode in sanity_modes:
                rows.append(_run_sanity(
                    data_sanity_check,
                    {**sample, "sanity_mode": sanity_mode},
                    str(sample.get("transcript") or ""),
                    form_data,
                    {},
                ))
    else:  # entities — rekonstrukcja formularza z gold-encji (offline)
        rows = []
        for sample in samples:
            expected = parse_entities(sample.get("expected_entities") or {})
            sample = {**sample, "synthetic": True, "gold_has_patient": bool(expected.get("patient"))}
            form_data = build_form_data(expected)
            for sanity_mode in sanity_modes:
                rows.append(_run_sanity(
                    data_sanity_check,
                    {**sample, "sanity_mode": sanity_mode},
                    str(sample.get("transcript") or ""),
                    form_data,
                    {},
                ))

    print(f"  format wejścia: {fmt}, sanity_modes={','.join(sanity_modes)}")
    write_rows(rows, output_dir / "end_to_end_results.csv", leading=("sample_id", "audio_file", "sanity_mode", "status", "score"))
    _summarize_sanity(rows)


def _summarize_sanity(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    frame = pd.DataFrame(rows)
    mode_groups = frame.groupby("sanity_mode", dropna=False) if "sanity_mode" in frame else [("", frame)]

    for sanity_mode, group in mode_groups:
        distribution = group["status"].value_counts().to_dict()
        mean_score = round(pd.to_numeric(group["score"], errors="coerce").mean(), 4)
        bucket_distribution = group["score_bucket"].value_counts().to_dict() if "score_bucket" in group else {}
        label = sanity_mode or "rules"
        print(
            f"  [{label}] podsumowanie: {len(group)} wierszy, statusy={distribution}, "
            f"score_bucket={bucket_distribution}, mean score={mean_score}"
        )

        evaluable = [row for row in group.to_dict("records") if isinstance(row.get("expected_flag"), bool)]
        if evaluable:
            tp = sum(1 for row in evaluable if row["expected_flag"] and row["status"] != "ok")
            tn = sum(1 for row in evaluable if not row["expected_flag"] and row["status"] == "ok")
            fp = sum(1 for row in evaluable if not row["expected_flag"] and row["status"] != "ok")
            fn = sum(1 for row in evaluable if row["expected_flag"] and row["status"] == "ok")
            print(f"  [{label}] zgodność z expected_flag: {tp + tn}/{len(evaluable)} (TP={tp} TN={tn} FP={fp} FN={fn})")

        severity_evaluable = [row for row in group.to_dict("records") if row.get("expected_severity")]
        if severity_evaluable:
            matches = sum(1 for row in severity_evaluable if bool(row.get("severity_match")))
            print(f"  [{label}] zgodność z expected_severity: {matches}/{len(severity_evaluable)}")

        issue_code_evaluable = [row for row in group.to_dict("records") if row.get("expected_issue_codes")]
        if issue_code_evaluable:
            matches = sum(1 for row in issue_code_evaluable if bool(row.get("issue_code_match")))
            print(f"  [{label}] zgodność z expected_issue_codes: {matches}/{len(issue_code_evaluable)}")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

STAGE_RUNNERS = {"stt": run_stt, "ner": run_ner, "end_to_end": run_end_to_end, "sanity": run_end_to_end}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Eval całego pipeline'u 4Diagnosis (konfiguracja w config.yaml).")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="ścieżka do config.yaml")
    parser.add_argument("--stages", nargs="+", default=None, help="nadpisuje stages z configu (stt / ner / end_to_end)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.config.exists():
        raise SystemExit(f"Brak pliku config: {args.config}")

    config = load_config(args.config)
    stages = args.stages if args.stages is not None else config.get("stages", [])
    output_dir = resolve_path(config["paths"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Config: {args.config}")
    print(f"Etapy: {', '.join(stages) or '(brak)'}\n")

    for stage in stages:
        runner = STAGE_RUNNERS.get(stage)
        if runner is None:
            print(f"[{stage}] nieznany etap — pomijam (dostępne: {', '.join(STAGE_RUNNERS)})")
            continue
        runner(config, output_dir)
        print()


if __name__ == "__main__":
    main()
