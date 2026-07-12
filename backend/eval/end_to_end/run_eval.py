from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import pandas as pd

EVAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL_ROOT))

from ner.metrics import compare_entities, flatten_metrics, parse_entities
from stt.metrics import compute_stt_metrics


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "backend/src"
DEFAULT_INPUT = REPO_ROOT / "backend/eval/results/stt_manifest.csv"
DEFAULT_OUTPUT = REPO_ROOT / "backend/eval/results/end_to_end_eval_results.csv"
DEFAULT_PREPROCESSED_DIR = REPO_ROOT / "backend/eval/results/preprocessed_audio/end_to_end"


def _load_pipeline_classes():
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))

    from app_stt.pipeline.config import PipelineConfig
    from app_stt.pipeline.pipeline import Pipeline
    return PipelineConfig, Pipeline


def _build_config(model: str, preprocessing: str, ner_strategy: str, llm_model: str):
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


def load_samples(path: Path, limit: int | None) -> pd.DataFrame:
    samples = pd.read_csv(path)
    required = {"audio_path", "audio_file"}
    missing = required - set(samples.columns)
    if missing:
        raise ValueError(f"End-to-end eval input missing columns: {', '.join(sorted(missing))}")
    if limit is not None:
        samples = samples.head(limit)
    return samples


def run_eval(args: argparse.Namespace) -> list[dict]:
    samples = load_samples(args.input, args.limit)
    _, Pipeline = _load_pipeline_classes()
    rows = []

    for model in args.models:
        for preprocessing in args.preprocessing:
            for ner_strategy in args.ner_strategies:
                config = _build_config(model, preprocessing, ner_strategy, args.llm_model)
                pipeline = Pipeline(config)

                for _, sample in samples.iterrows():
                    row = {
                        "sample_id": sample.get("sample_id", ""),
                        "audio_file": sample["audio_file"],
                        "model": model,
                        "preprocessing": preprocessing,
                        "ner_strategy": ner_strategy,
                        "llm_model": args.llm_model,
                        "status": "ok",
                        "error": "",
                        "reference": sample.get("ref_transcript", ""),
                        "transcript": "",
                        "expected_entities": sample.get("expected_entities", ""),
                        "predicted_entities": "",
                    }

                    start = time.perf_counter()
                    try:
                        result = pipeline.run(str(sample["audio_path"]))
                        duration = time.perf_counter() - start
                        transcript = result.get("transcript", "")
                        predicted_entities = result.get("entities", {}) or {}

                        row.update({
                            "transcript": transcript,
                            "predicted_entities": json.dumps(predicted_entities, ensure_ascii=False, sort_keys=True),
                            "duration_seconds": round(duration, 4),
                        })

                        reference = sample.get("ref_transcript", "")
                        if isinstance(reference, str) and reference.strip():
                            stt_metrics = compute_stt_metrics(reference, transcript)
                            row.update({f"stt_{key}": value for key, value in stt_metrics.items()})

                        expected_entities = sample.get("expected_entities", "")
                        if isinstance(expected_entities, str) and expected_entities.strip():
                            ner_metrics = compare_entities(parse_entities(expected_entities), predicted_entities)
                            row.update({f"ner_{key}": value for key, value in flatten_metrics(ner_metrics).items()})
                    except Exception as exc:
                        duration = time.perf_counter() - start
                        row.update({
                            "status": "error",
                            "error": str(exc),
                            "duration_seconds": round(duration, 4),
                        })

                    rows.append(row)

    return rows


def write_results(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run end-to-end audio -> STT -> NER evaluation.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--models", nargs="+", default=["whisper-small"])
    parser.add_argument("--preprocessing", nargs="+", default=["baseline"])
    parser.add_argument("--ner-strategies", nargs="+", default=["chained"])
    parser.add_argument("--llm-model", default="openai/gpt-4o")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(f"End-to-end eval input file does not exist: {args.input}")

    rows = run_eval(args)
    write_results(rows, args.output)
    print(f"Wrote end-to-end eval results: {args.output}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main()
