from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CURRENT = REPO_ROOT / "backend/eval/results/stt_eval_results.csv"
DEFAULT_BASELINE = REPO_ROOT / "backend/eval/baselines/stt/whisper_comparison_results.csv"
DEFAULT_OUTPUT = REPO_ROOT / "backend/eval/results/stt_baseline_comparison.csv"


def _load_current(path: Path) -> pd.DataFrame:
    current = pd.read_csv(path)
    required = {"model", "audio_file", "wer"}
    missing = required - set(current.columns)
    if missing:
        raise ValueError(f"Current results missing columns: {', '.join(sorted(missing))}")

    current = current.copy()
    current["audio_file"] = current["audio_file"].astype(str)
    current["current_wer"] = pd.to_numeric(current["wer"], errors="coerce")
    current["current_cer"] = pd.to_numeric(current.get("cer"), errors="coerce")
    current["current_duration_seconds"] = pd.to_numeric(
        current.get("duration_seconds"),
        errors="coerce",
    )
    return current


def _load_baseline(path: Path) -> pd.DataFrame:
    baseline = pd.read_csv(path, encoding="utf-8-sig")
    required = {"model", "plik", "WER"}
    missing = required - set(baseline.columns)
    if missing:
        raise ValueError(f"Baseline results missing columns: {', '.join(sorted(missing))}")

    baseline = baseline.copy()
    baseline["audio_file"] = baseline["plik"].astype(str)
    baseline["baseline_wer"] = pd.to_numeric(baseline["WER"], errors="coerce")
    baseline["baseline_duration_seconds"] = pd.to_numeric(
        baseline.get("czas_s"),
        errors="coerce",
    )
    return baseline


def compare_results(current: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    merged = current.merge(
        baseline,
        on=["model", "audio_file"],
        how="inner",
        suffixes=("_current", "_baseline"),
    )

    columns = [
        "model",
        "audio_file",
        "preprocessing",
        "status",
        "baseline_wer",
        "current_wer",
        "current_cer",
        "baseline_duration_seconds",
        "current_duration_seconds",
    ]
    available_columns = [column for column in columns if column in merged.columns]
    comparison = merged[available_columns].copy()

    comparison["wer_delta"] = comparison["current_wer"] - comparison["baseline_wer"]
    comparison["wer_relative_delta"] = comparison["wer_delta"] / comparison["baseline_wer"]

    if {"current_duration_seconds", "baseline_duration_seconds"}.issubset(comparison.columns):
        comparison["duration_delta_seconds"] = (
            comparison["current_duration_seconds"] - comparison["baseline_duration_seconds"]
        )

    sort_columns = [column for column in ["model", "audio_file", "preprocessing"] if column in comparison.columns]
    comparison = comparison.sort_values(sort_columns, na_position="last")
    return comparison.reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare current STT eval results with historical baseline.")
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.current.exists():
        raise SystemExit(f"Current results file does not exist: {args.current}")
    if not args.baseline.exists():
        raise SystemExit(f"Baseline file does not exist: {args.baseline}")

    comparison = compare_results(_load_current(args.current), _load_baseline(args.baseline))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(args.output, index=False)

    print(f"Wrote STT baseline comparison: {args.output}")
    print(f"Rows: {len(comparison)}")


if __name__ == "__main__":
    main()
