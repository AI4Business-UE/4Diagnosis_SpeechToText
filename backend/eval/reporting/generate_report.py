from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STT_SUMMARY = REPO_ROOT / "backend/eval/results/stt_eval_summary.csv"
DEFAULT_STT_BASELINE_COMPARISON = REPO_ROOT / "backend/eval/results/stt_baseline_comparison.csv"
DEFAULT_NER_SUMMARY = REPO_ROOT / "backend/eval/results/ner_eval_summary.csv"
DEFAULT_OUTPUT = REPO_ROOT / "backend/eval/results/eval_report.md"


def _format_value(value) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _markdown_table(frame: pd.DataFrame, columns: list[str], limit: int = 10) -> str:
    available = [column for column in columns if column in frame.columns]
    if not available:
        return "_Brak pasujących kolumn do pokazania._"

    view = frame[available].head(limit)
    lines = [
        "| " + " | ".join(available) + " |",
        "| " + " | ".join(["---"] * len(available)) + " |",
    ]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(_format_value(row[column]) for column in available) + " |")
    return "\n".join(lines)


def _section_from_csv(path: Path, title: str, columns: list[str]) -> str:
    if not path.exists():
        return f"## {title}\n\n_Brak pliku: `{path}`._\n"

    frame = pd.read_csv(path)
    return f"## {title}\n\n{_markdown_table(frame, columns)}\n"


def build_report(args: argparse.Namespace) -> str:
    sections = [
        "# Raport ewaluacji STT / NER",
        "Ten raport zbiera lokalne wyniki evala. Traktujemy go jako materiał data-science, nie jako decyzję produkcyjną.",
        _section_from_csv(
            args.stt_summary,
            "STT summary",
            [
                "model",
                "preprocessing",
                "samples_count",
                "errors_count",
                "mean_wer",
                "mean_cer",
                "mean_medical_term_recall",
                "critical_samples_count",
                "mean_real_time_factor",
            ],
        ),
        _section_from_csv(
            args.stt_baseline_comparison,
            "STT vs baseline",
            [
                "model",
                "audio_file",
                "preprocessing",
                "baseline_wer",
                "current_wer",
                "wer_delta",
                "duration_delta_seconds",
            ],
        ),
        _section_from_csv(
            args.ner_summary,
            "NER summary",
            [
                "strategy",
                "model",
                "samples_count",
                "errors_count",
                "mean_overall_precision",
                "mean_overall_recall",
                "mean_overall_f1",
                "mean_duration_seconds",
            ],
        ),
        "## Ograniczenia\n\n- Wyniki zależą od rozmiaru i jakości lokalnego zbioru.\n- Małe runy (`--limit`) traktujemy tylko jako smoke/data sanity, nie jako finalną rekomendację.\n- NER używa LLM, więc pełny eval może generować koszt i wymaga świadomego uruchomienia.\n",
    ]
    return "\n\n".join(sections).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a simple markdown report from eval summaries.")
    parser.add_argument("--stt-summary", type=Path, default=DEFAULT_STT_SUMMARY)
    parser.add_argument("--stt-baseline-comparison", type=Path, default=DEFAULT_STT_BASELINE_COMPARISON)
    parser.add_argument("--ner-summary", type=Path, default=DEFAULT_NER_SUMMARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")

    print(f"Wrote eval report: {args.output}")


if __name__ == "__main__":
    main()
