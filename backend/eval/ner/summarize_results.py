from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = REPO_ROOT / "backend/eval/results/ner_eval_results.csv"
DEFAULT_OUTPUT = REPO_ROOT / "backend/eval/results/ner_eval_summary.csv"
GROUP_COLUMNS = ["strategy", "model"]
ENTITY_TYPES = ["overall", "patient", "components", "lesions", "fluid_samples"]
METRICS = ["precision", "recall", "f1", "tp", "fp", "fn"]


def _numeric_columns(results: pd.DataFrame) -> list[str]:
    columns = ["duration_seconds"]
    for entity_type in ENTITY_TYPES:
        for metric in METRICS:
            column = f"{entity_type}_{metric}"
            if column in results.columns:
                columns.append(column)
    return columns


def _as_numeric(results: pd.DataFrame) -> pd.DataFrame:
    results = results.copy()
    for column in _numeric_columns(results):
        results[column] = pd.to_numeric(results[column], errors="coerce")
    return results


def _mean(group: pd.DataFrame, column: str) -> float | None:
    if column not in group:
        return None
    values = group[column].dropna()
    if values.empty:
        return None
    return float(values.mean())


def _sum(group: pd.DataFrame, column: str) -> int | None:
    if column not in group:
        return None
    values = group[column].dropna()
    if values.empty:
        return None
    return int(values.sum())


def summarize_results(results: pd.DataFrame) -> pd.DataFrame:
    missing_columns = [column for column in GROUP_COLUMNS if column not in results.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    results = _as_numeric(results)
    rows = []

    for (strategy, model), group in results.groupby(GROUP_COLUMNS, dropna=False):
        status = group.get("status")
        errors_count = int((status == "error").sum()) if status is not None else 0
        row = {
            "strategy": strategy,
            "model": model,
            "samples_count": len(group),
            "errors_count": errors_count,
            "mean_duration_seconds": _mean(group, "duration_seconds"),
        }

        for entity_type in ENTITY_TYPES:
            for metric in ["precision", "recall", "f1"]:
                row[f"mean_{entity_type}_{metric}"] = _mean(group, f"{entity_type}_{metric}")
            for metric in ["tp", "fp", "fn"]:
                row[f"sum_{entity_type}_{metric}"] = _sum(group, f"{entity_type}_{metric}")

        rows.append(row)

    summary = pd.DataFrame(rows)
    sort_columns = [
        column
        for column in ["mean_overall_f1", "mean_overall_recall", "mean_duration_seconds"]
        if column in summary.columns
    ]
    if sort_columns:
        summary = summary.sort_values(
            sort_columns,
            ascending=[False, False, True][:len(sort_columns)],
            na_position="last",
        )

    return summary.reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize NER evaluation results.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(
            f"Input file does not exist: {args.input}\n"
            "Run backend/eval/ner/run_eval.py first to generate raw NER evaluation results."
        )

    results = pd.read_csv(args.input)
    summary = summarize_results(results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.output, index=False)

    print(f"Wrote NER eval summary: {args.output}")
    print(f"Rows: {len(summary)}")


if __name__ == "__main__":
    main()
