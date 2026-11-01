from __future__ import annotations

import argparse
import dataclasses
import enum
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from .dataset import initialize_reference_template, load_dataset
from .report import default_report_path, save_report
from .runner import run_evaluation

BACKEND_DIR = Path(__file__).resolve().parents[2]
EVAL_DIR = BACKEND_DIR / "eval"
DATA_DIR = EVAL_DIR / "data" / "golden_dataset"
_WHISPER_MODELS = (
    "whisper-small",
    "whisper-medium",
    "whisper-medical-pl",
    "whisper-large-v3",
    "whisper-large-v3-turbo",
)


@dataclass(frozen=True)
class EvaluationRuntime:
    pipeline_factory: Callable[[], Any]
    resolved_config: dict[str, Any]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Uruchamia lokalną ewaluację end-to-end transkrypcji.",
    )
    parser.add_argument("--metadata", type=Path, default=DATA_DIR / "samples_metadata.xlsx")
    parser.add_argument("--audio-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--ner-references", type=Path, default=DATA_DIR / "ner_references.json")
    parser.add_argument("--init-ner-references", action="store_true", help="Utwórz lokalny szablon adnotacji NER i zakończ.")
    parser.add_argument("--samples", type=_parse_sample_ids, help="Lista identyfikatorów, np. 001,004,020; domyślnie wszystkie.")
    parser.add_argument("--stt-model", choices=("whisper_local", "whisper_hosted", "gpt-transcribe"))
    parser.add_argument(
        "--whisper-model",
        choices=_WHISPER_MODELS,
        help="Id modelu Whisper używany przy modelach Whisper.",
    )
    parser.add_argument("--ner-strategy", choices=("chained", "split"))
    parser.add_argument("--judge-model", default=os.getenv("EVAL_JUDGE_MODEL"))
    parser.add_argument("--no-judge", action="store_true", help="Pomiń ocenę LLM corrected_transcript.")
    parser.add_argument("--include-details", action="store_true", help="Zapisz lokalnie teksty kliniczne i uzasadnienia oceny.")
    parser.add_argument("--output", type=Path, help="Ścieżka nowego pliku raportu JSON.")
    parser.add_argument(
        "--allow-external-data",
        action="store_true",
        help="Potwierdź, że dostawcy zewnętrzni są zatwierdzeni do przetwarzania tych nagrań i tekstów klinicznych.",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    dataset_loader: Callable[..., Any] | None = None,
    runtime_factory: Callable[[argparse.Namespace], EvaluationRuntime] | None = None,
    evaluator: Callable[..., dict[str, Any]] | None = None,
    report_writer: Callable[..., Path] | None = None,
    output: Callable[[str], None] | None = None,
    error_output: Callable[[str], None] | None = None,
) -> int:
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv(BACKEND_DIR / "src" / ".env")
    parser = build_parser()
    args = parser.parse_args(argv)
    output = output or print
    error_output = error_output or (lambda message: print(message, file=sys.stderr))

    if args.init_ner_references:
        try:
            path = initialize_reference_template(args.metadata, args.ner_references)
        except Exception as error:
            error_output(f"Nie udało się utworzyć szablonu NER ({type(error).__name__}).")
            return 1
        output(f"Utworzono lokalny szablon NER: {path}")
        output("Uzupełnij adnotacje i ustaw reviewed=true dla każdego sprawdzonego rekordu.")
        return 0

    if not args.allow_external_data:
        parser.error(
            "Pełna ewaluacja wysyła audio i tekst kliniczny do skonfigurowanych usług. "
            "Użyj --allow-external-data wyłącznie po potwierdzeniu, że dostawcy są zatwierdzeni."
        )
    if args.include_details:
        output("Uwaga: szczegółowy raport zawiera teksty kliniczne i powinien pozostać lokalny.")
    judge_enabled = not args.no_judge
    if judge_enabled and not args.judge_model:
        parser.error("Ocena LLM wymaga jawnego modelu: ustaw EVAL_JUDGE_MODEL lub podaj --judge-model.")

    try:
        loader = dataset_loader or load_dataset
        samples = loader(
            args.metadata,
            args.audio_dir,
            args.ner_references,
            sample_ids=args.samples,
        )
        runtime = (runtime_factory or prepare_runtime)(args)
        report = (evaluator or run_evaluation)(
            samples,
            pipeline_factory=runtime.pipeline_factory,
            judge_model=args.judge_model,
            judge_enabled=judge_enabled,
            include_details=args.include_details,
            resolved_config=runtime.resolved_config,
        )
        report_path = args.output or default_report_path(EVAL_DIR)
        saved_path = (report_writer or save_report)(
            report,
            report_path,
            include_details=args.include_details,
        )
    except Exception as error:
        error_output(_safe_error(error))
        return 1

    output(
        f"Ewaluacja: {'kompletna' if report['status'] == 'complete' else 'niekompletna'} | próbki: "
        f"{report['pipeline_samples_completed']}/{report['samples_requested']} | "
        f"WER: {_display_metric(report['transcript'].get('wer'))} | "
        f"CER: {_display_metric(report['transcript'].get('cer'))} | "
        f"NER exact: {_display_metric(report['ner'].get('exact_record_rate'))} | "
        f"sędzia: {_display_metric(report['judge'].get('mean_score'))}"
    )
    output(f"Raport JSON: {saved_path}")
    if report["errors"]:
        error_output(f"Niekompletna ewaluacja: wystąpiły błędy w {len(report['errors'])} etapach lub próbkach.")
    return 0 if report["status"] == "complete" else 1


def prepare_runtime(args: argparse.Namespace) -> EvaluationRuntime:
    """Bootstrap Django without its test runner, then isolate and seed in-memory RAG."""
    source_dir = BACKEND_DIR / "src"
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stt.settings")
    # Prevent AppSttConfig.ready() from constructing the web application's singleton
    # pipeline while still allowing the STT stage to read the Keyword model.
    os.environ["TESTING"] = "1"
    import django

    django.setup()

    from app_stt.pipeline.config import PipelineConfig
    from app_stt.pipeline.pipeline import Pipeline
    from app_stt.pipeline.stages.rag.qdrant import (QdrantClientMode,
                                                    index_database)

    config_values: dict[str, Any] = {"qdrant_client_mode": QdrantClientMode.IN_MEMORY}
    for argument, field in (
        ("stt_model", "stt_model"),
        ("whisper_model", "whisper_model"),
        ("ner_strategy", "ner_strategy"),
    ):
        value = getattr(args, argument, None)
        if value is not None:
            config_values[field] = value
    config = PipelineConfig(**config_values)
    whisper_hf_id = config.whisper_hf_id

    if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")):
        raise ValueError("Brak klucza OPENROUTER_API_KEY lub OPENAI_API_KEY.")

    index_database(config)
    resolved_config = {
        field.name: _json_config_value(getattr(config, field.name))
        for field in dataclasses.fields(config)
    }
    resolved_config["whisper_hf_id"] = whisper_hf_id
    resolved_config["stt_model_id"] = (
        "openai/gpt-transcribe" if config.stt_model == "gpt-transcribe" else whisper_hf_id
    )
    resolved_config["llm_api_provider"] = "openrouter" if os.getenv("OPENROUTER_API_KEY") else "openai"
    return EvaluationRuntime(
        pipeline_factory=lambda: Pipeline(config),
        resolved_config=resolved_config,
    )


def _parse_sample_ids(value: str) -> list[str]:
    sample_ids = [sample_id.strip() for sample_id in value.split(",") if sample_id.strip()]
    if not sample_ids:
        raise argparse.ArgumentTypeError("Wskaż co najmniej jeden identyfikator próbki.")
    return sample_ids


def _json_config_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "name"):
        return value.name
    return str(value)


def _display_metric(value: Any) -> str:
    return "brak" if value is None else str(value)


def _safe_error(error: Exception) -> str:
    if isinstance(error, (ValueError, FileNotFoundError, FileExistsError)):
        return f"Błąd ewaluacji: {error}"
    return f"Błąd ewaluacji ({type(error).__name__}); szczegóły pominięto ze względu na dane kliniczne."
