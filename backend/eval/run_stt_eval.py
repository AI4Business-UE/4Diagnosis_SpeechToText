from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from stt_metrics import compute_stt_metrics


REPO_ROOT = Path(__file__).resolve().parents[2]


DEFAULT_MANIFEST = REPO_ROOT / "backend/eval/results/stt_manifest.csv"
DEFAULT_OUTPUT = REPO_ROOT / "backend/eval/results/stt_eval_results.csv"
DEFAULT_PREPROCESSED_DIR = REPO_ROOT / "backend/eval/results/preprocessed_audio"

WHISPER_MODELS = {
    "whisper-small": "openai/whisper-small",
    "whisper-medium": "openai/whisper-medium",
    "whisper-medical-pl": "msxksm/whisper-medium-medical-pl",
    "whisper-large-v3": "openai/whisper-large-v3",
}


@dataclass
class EvalPipelineConfig:
    whisper_model: str = "whisper-small"
    target_sr: int = 16000
    use_volume_normalization: bool = True
    use_bandpass_filter: bool = False
    use_noise_reduction: bool = False
    use_vad: bool = False
    use_salt_augmentation: bool = False
    volume_target_peak: float = 0.95
    high_pass_hz: int = 200
    low_pass_hz: int = 7900
    filter_order: int = 4
    noise_reduction_stationary: bool = False
    noise_reduction_prop_decrease: float = 0.8
    vad_threshold: float = 0.5
    vad_min_speech_duration_ms: int = 250
    vad_min_silence_duration_ms: int = 100
    vad_speech_pad_ms: int = 200
    preprocessing_output_dir: str = str(DEFAULT_PREPROCESSED_DIR)

    @property
    def whisper_hf_id(self) -> str:
        return WHISPER_MODELS[self.whisper_model]


def _load_class(module_path: Path, module_name: str, class_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, class_name)


def load_audio_preprocessor():
    return _load_class(
        REPO_ROOT / "backend/src/app_stt/pipeline/stages/preprocessing.py",
        "eval_audio_preprocessing",
        "AudioPreprocessor",
    )


def load_whisper_local():
    return _load_class(
        REPO_ROOT / "backend/src/app_stt/pipeline/stages/stt/whisper_local.py",
        "eval_whisper_local",
        "WhisperLocal",
    )


def build_config(model_key: str, preprocessing_name: str) -> EvalPipelineConfig:
    config = EvalPipelineConfig(
        whisper_model=model_key,
        preprocessing_output_dir=str(DEFAULT_PREPROCESSED_DIR / preprocessing_name),
    )

    if preprocessing_name == "baseline":
        return config
    if preprocessing_name == "volume_norm":
        config.use_volume_normalization = True
        config.use_bandpass_filter = False
        config.use_noise_reduction = False
        config.use_vad = False
        return config
    if preprocessing_name == "vad":
        config.use_vad = True
        return config
    if preprocessing_name == "noise_reduction":
        config.use_noise_reduction = True
        return config
    if preprocessing_name == "bandpass":
        config.use_bandpass_filter = True
        return config

    raise ValueError(f"Unknown preprocessing config: {preprocessing_name}")


def load_manifest(path: Path, limit: int | None) -> pd.DataFrame:
    manifest = pd.read_csv(path)
    manifest = manifest[manifest["audio_exists"].astype(bool)]
    if limit is not None:
        manifest = manifest.head(limit)
    return manifest


def transcribe_one(
    stt_model,
    audio_path: str,
    config: EvalPipelineConfig,
) -> tuple[str, dict, float, float]:
    AudioPreprocessor = load_audio_preprocessor()
    preprocessor = AudioPreprocessor(config)

    preprocessing_start = time.perf_counter()
    preprocessing_meta = preprocessor.process(audio_path)
    preprocessing_duration = time.perf_counter() - preprocessing_start

    stt_start = time.perf_counter()
    stt_result = stt_model.transcribe(preprocessing_meta["output_path"])
    stt_duration = time.perf_counter() - stt_start

    transcript = stt_result.get("text", "") if isinstance(stt_result, dict) else str(stt_result)
    return transcript, preprocessing_meta, preprocessing_duration, stt_duration


def run_eval(args: argparse.Namespace) -> list[dict]:
    manifest = load_manifest(args.manifest, args.limit)
    rows = []
    WhisperLocal = load_whisper_local()

    for model_key in args.models:
        model_config = EvalPipelineConfig(whisper_model=model_key)
        stt_model = WhisperLocal(model_id=model_config.whisper_hf_id)

        for preprocessing_name in args.preprocessing:
            config = build_config(model_key, preprocessing_name)

            for _, sample in manifest.iterrows():
                row = {
                    "sample_id": sample.get("sample_id", ""),
                    "audio_file": sample["audio_file"],
                    "model": model_key,
                    "preprocessing": preprocessing_name,
                    "reference": sample["ref_transcript"],
                    "transcript": "",
                    "status": "ok",
                    "error": "",
                }

                try:
                    transcript, preprocessing_meta, preprocessing_duration, stt_duration = transcribe_one(
                        stt_model,
                        sample["audio_path"],
                        config,
                    )
                    metrics = compute_stt_metrics(sample["ref_transcript"], transcript)
                    audio_duration = float(preprocessing_meta.get("original_duration_seconds") or 0)
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
                except Exception as exc:
                    row.update({
                        "status": "error",
                        "error": str(exc),
                    })

                rows.append(row)

    return rows


def write_results(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local STT evaluation.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--models", nargs="+", default=["whisper-small"])
    parser.add_argument("--preprocessing", nargs="+", default=["baseline"])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = run_eval(args)
    write_results(rows, args.output)
    print(f"Wrote STT eval results: {args.output}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main()
