from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = REPO_ROOT / "backend/eval/results/sanity_eval_results.csv"
DEFAULT_OUTPUT = REPO_ROOT / "backend/eval/results/sanity_eval_summary.csv"

# Grupujemy przede wszystkim po trybie (rules / rules_and_llm / llm_only), a jeśli
# wyniki pochodzą z pipeline'u audio — dokładamy model/preprocessing.
BASE_GROUP_COLUMNS = ["mode"]
OPTIONAL_GROUP_COLUMNS = ["pipeline_model", "preprocessing"]

NUMERIC_COLUMNS = [
    "score",
    "issue_count",
    "warning_count",
    "error_count",
    "rules_issue_count",
    "llm_issue_count",
    "filtered_synthetic_issues",
]


def _group_columns(results: pd.DataFrame) -> list[str]:
    columns = [column for column in BASE_GROUP_COLUMNS if column in results.columns]
    for column in OPTIONAL_GROUP_COLUMNS:
        if column in results.columns and results[column].astype(str).str.strip().any():
            columns.append(column)
    return columns or BASE_GROUP_COLUMNS


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


def _status_count(group: pd.DataFrame, status: str) -> int:
    if "status" not in group:
        return 0
    return int((group["status"].astype(str) == status).sum())


def _true_count(group: pd.DataFrame, column: str) -> int:
    if column not in group:
        return 0
    normalized = group[column].astype(str).str.lower().str.strip()
    return int(normalized.isin(["true", "1", "yes"]).sum())


def summarize_results(results: pd.DataFrame) -> pd.DataFrame:
    missing_columns = [column for column in BASE_GROUP_COLUMNS if column not in results.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    group_columns = _group_columns(results)
    results = _as_numeric(results)
    rows = []

    for keys, group in results.groupby(group_columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)

        row = dict(zip(group_columns, keys))
        row.update({
            "samples_count": len(group),
            "status_ok": _status_count(group, "ok"),
            "status_warning": _status_count(group, "warning"),
            "status_critical": _status_count(group, "critical"),
            "llm_ran_count": _true_count(group, "llm_ran"),
            "mean_score": _mean(group, "score"),
            "mean_issue_count": _mean(group, "issue_count"),
            "mean_warning_count": _mean(group, "warning_count"),
            "mean_error_count": _mean(group, "error_count"),
            "mean_rules_issue_count": _mean(group, "rules_issue_count"),
            "mean_llm_issue_count": _mean(group, "llm_issue_count"),
            "mean_filtered_synthetic_issues": _mean(group, "filtered_synthetic_issues"),
        })
        rows.append(row)

    summary = pd.DataFrame(rows)
    if "mode" in summary.columns:
        summary = summary.sort_values(group_columns, na_position="last")

    return summary.reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize data sanity check evaluation results per mode.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(
            f"Input file does not exist: {args.input}\n"
            "Run backend/eval/sanity/run_eval.py first to generate raw sanity evaluation results."
        )

    results = pd.read_csv(args.input)
    summary = summarize_results(results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.output, index=False)

    print(f"Wrote sanity eval summary: {args.output}")
    print(f"Rows: {len(summary)}")


if __name__ == "__main__":
    main()
