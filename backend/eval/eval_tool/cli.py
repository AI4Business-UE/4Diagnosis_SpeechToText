from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from .dataset import load_dataset
from .report import (default_report_path, default_review_workbook_path,
                     save_report, save_review_workbook)
from .runner import run_evaluation
from .runtime import BACKEND_DIR, EvaluationRuntime, prepare_runtime

EVAL_DIR = BACKEND_DIR / "eval"
DATA_DIR = EVAL_DIR / "data" / "golden_dataset"

_UNRECOGNIZED_PREFIX = "unrecognized arguments: "


class _PolishArgumentParser(argparse.ArgumentParser):
    """Surface argparse failures in Polish, consistent with the rest of the CLI."""

    def error(self, message: str) -> None:
        if message.startswith(_UNRECOGNIZED_PREFIX):
            message = (
                f"Nieznane argumenty: {message.removeprefix(_UNRECOGNIZED_PREFIX)}. "
                "Ocena referencji Gold NER została usunięta; wynik metadanych pacjenta "
                "jest liczony automatycznie."
            )
        super().error(message)


def build_parser() -> argparse.ArgumentParser:
    parser = _PolishArgumentParser(
        description="Uruchamia lokalną ewaluację end-to-end transkrypcji.",
    )
    parser.add_argument("--metadata", type=Path, default=DATA_DIR / "samples_metadata.xlsx")
    parser.add_argument("--audio-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--samples", type=_parse_sample_ids, help="Lista identyfikatorów, np. 001,004,020; domyślnie wszystkie.")
    parser.add_argument("--stt-model", choices=("whisper_local", "whisper_hosted", "gpt-transcribe"))
    parser.add_argument(
        "--whisper-model",
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
    workbook_writer: Callable[..., Path] | None = None,
    output: Callable[[str], None] | None = None,
    error_output: Callable[[str], None] | None = None,
) -> int:
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv(BACKEND_DIR / "src" / ".env")
    parser = build_parser()
    args = parser.parse_args(argv)
    output = output or print
    error_output = error_output or (lambda message: print(message, file=sys.stderr))

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
    if args.include_details:
        results_dir = (EVAL_DIR / "results").resolve()
        output_path = (args.output or default_report_path(EVAL_DIR)).resolve()
        if not output_path.is_relative_to(results_dir):
            parser.error("Raport szczegółowy musi być zapisany w ignorowanym katalogu eval/results/.")

    try:
        loader = dataset_loader or load_dataset
        samples = loader(
            args.metadata,
            args.audio_dir,
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
        saved_workbook_path = (workbook_writer or save_review_workbook)(
            report.get("review_rows", []),
            default_review_workbook_path(EVAL_DIR),
        )
    except Exception as error:
        error_output(_safe_error(error))
        return 1

    metadata_summary = report.get("patient_metadata") or {}
    metadata_segment = ""
    if metadata_summary.get("samples"):
        metadata_segment = (
            f" | metadane pacjenta: {_display_metric(metadata_summary.get('mean_score'))}"
            f" ({metadata_summary['samples']} próbek)"
        )
    output(
        f"Ewaluacja: {'kompletna' if report['status'] == 'complete' else 'niekompletna'} | próbki: "
        f"{report['pipeline_samples_completed']}/{report['samples_requested']} | "
        f"WER: {_display_metric(report['transcript'].get('wer'))} | "
        f"CER: {_display_metric(report['transcript'].get('cer'))} | "
        f"sędzia: {_display_metric(report['judge'].get('mean_score'))}{metadata_segment}"
    )
    output(f"Raport JSON: {saved_path}")
    output(f"Arkusz przeglądu: {saved_workbook_path}")
    if report["errors"]:
        error_output(f"Niekompletna ewaluacja: wystąpiły błędy w {len(report['errors'])} etapach lub próbkach.")
    return 0 if report["status"] == "complete" else 1


def _parse_sample_ids(value: str) -> list[str]:
    sample_ids = [sample_id.strip() for sample_id in value.split(",") if sample_id.strip()]
    if not sample_ids:
        raise argparse.ArgumentTypeError("Wskaż co najmniej jeden identyfikator próbki.")
    return sample_ids


def _display_metric(value: Any) -> str:
    return "brak" if value is None else str(value)


def _safe_error(error: Exception) -> str:
    if isinstance(error, (ValueError, FileNotFoundError, FileExistsError)):
        return f"Błąd ewaluacji: {error}"
    return f"Błąd ewaluacji ({type(error).__name__}); szczegóły pominięto ze względu na dane kliniczne."
