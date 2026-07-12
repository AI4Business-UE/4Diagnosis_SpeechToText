from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = REPO_ROOT / "backend/eval/results/stt_eval_results.csv"
DEFAULT_OUTPUT = REPO_ROOT / "backend/eval/results/stt_eval_summary.csv"

GROUP_COLUMNS = ["model", "preprocessing"]
NUMERIC_COLUMNS = [
    "wer",
    "cer",
    "wer_strict",
    "cer_strict",
    "number_recall",
    "number_precision",
    "dimension_recall",
    "dimension_precision",
    "medical_term_recall",
    "pesel_accuracy",
    "critical_error_count",
    "duration_seconds",
    "audio_duration_seconds",
    "real_time_factor",
]


def _as_numeric(results: pd.DataFrame) -> pd.DataFrame:
    results = results.copy()
    for column in NUMERIC_COLUMNS:
        if column in results.columns:
            results[column] = pd.to_numeric(results[column], errors="coerce")
    return results


def _mean(group: pd.DataFrame, column: str) -> float | None:
    if column not in group:
        return None
    values = group[column].dropna()
    if values.empty:
        return None
    return float(values.mean())


def _median(group: pd.DataFrame, column: str) -> float | None:
    if column not in group:
        return None
    values = group[column].dropna()
    if values.empty:
        return None
    return float(values.median())


def _true_count(group: pd.DataFrame, column: str) -> int:
    if column not in group:
        return 0

    values = group[column].fillna(False)
    if values.dtype == bool:
        return int(values.sum())

    normalized = values.astype(str).str.lower().str.strip()
    return int(normalized.isin(["true", "1", "yes"]).sum())


def summarize_results(results: pd.DataFrame) -> pd.DataFrame:
    missing_columns = [column for column in GROUP_COLUMNS if column not in results.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    results = _as_numeric(results)
    rows = []

    for (model, preprocessing), group in results.groupby(GROUP_COLUMNS, dropna=False):
        status = group.get("status")
        errors_count = int((status == "error").sum()) if status is not None else 0

        row = {
            "model": model,
            "preprocessing": preprocessing,
            "samples_count": len(group),
            "errors_count": errors_count,
            "mean_wer": _mean(group, "wer"),
            "median_wer": _median(group, "wer"),
            "mean_cer": _mean(group, "cer"),
            "median_cer": _median(group, "cer"),
            "mean_wer_strict": _mean(group, "wer_strict"),
            "mean_cer_strict": _mean(group, "cer_strict"),
            "mean_number_recall": _mean(group, "number_recall"),
            "mean_number_precision": _mean(group, "number_precision"),
            "mean_dimension_recall": _mean(group, "dimension_recall"),
            "mean_dimension_precision": _mean(group, "dimension_precision"),
            "mean_medical_term_recall": _mean(group, "medical_term_recall"),
            "mean_pesel_accuracy": _mean(group, "pesel_accuracy"),
            "critical_samples_count": _true_count(group, "has_critical_error"),
            "mean_critical_error_count": _mean(group, "critical_error_count"),
            "spurious_number_samples_count": _true_count(group, "has_spurious_number"),
            "term_error_samples_count": _true_count(group, "has_term_error"),
            "mean_duration_seconds": _mean(group, "duration_seconds"),
            "mean_audio_duration_seconds": _mean(group, "audio_duration_seconds"),
            "mean_real_time_factor": _mean(group, "real_time_factor"),
        }
        rows.append(row)

    summary = pd.DataFrame(rows)
    sort_columns = [
        column
        for column in ["mean_wer", "mean_cer", "mean_real_time_factor"]
        if column in summary.columns
    ]
    if sort_columns:
        summary = summary.sort_values(sort_columns, na_position="last")

    return summary.reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize local STT evaluation results.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.input.exists():
        raise SystemExit(
            f"Input file does not exist: {args.input}\n"
            "Run backend/eval/stt/run_eval.py first to generate raw STT evaluation results."
        )

    results = pd.read_csv(args.input)
    summary = summarize_results(results)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.output, index=False)

    print(f"Wrote STT eval summary: {args.output}")
    print(f"Rows: {len(summary)}")


if __name__ == "__main__":
    main()
