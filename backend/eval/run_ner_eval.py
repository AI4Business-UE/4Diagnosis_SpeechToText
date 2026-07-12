from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import pandas as pd

from ner_metrics import compare_entities, flatten_metrics, parse_entities


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "backend/src"
DEFAULT_INPUT = REPO_ROOT / "backend/eval/data/ner/ner_eval_samples.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "backend/eval/results/ner_eval_results.csv"


def _load_strategy(strategy_name: str, model: str):
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))

    if strategy_name == "chained":
        from app_stt.pipeline.stages.ner.chained import ChainedNERStrategy
        return ChainedNERStrategy(model=model)
    if strategy_name == "split":
        from app_stt.pipeline.stages.ner.split import SplitNERStrategy
        return SplitNERStrategy(model=model)

    raise ValueError(f"Unknown NER strategy: {strategy_name}")


def _read_jsonl(path: Path) -> pd.DataFrame:
    rows = []
    with path.open(encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            row.setdefault("sample_id", line_number)
            rows.append(row)
    return pd.DataFrame(rows)


def load_samples(path: Path, limit: int | None) -> pd.DataFrame:
    if path.suffix.lower() == ".jsonl":
        samples = _read_jsonl(path)
    else:
        samples = pd.read_csv(path)

    required = {"transcript", "expected_entities"}
    missing = required - set(samples.columns)
    if missing:
        raise ValueError(f"NER eval input missing columns: {', '.join(sorted(missing))}")

    if limit is not None:
        samples = samples.head(limit)
    return samples


def run_eval(args: argparse.Namespace) -> list[dict]:
    samples = load_samples(args.input, args.limit)
    rows = []

    for strategy_name in args.strategies:
        strategy = _load_strategy(strategy_name, args.model)

        for _, sample in samples.iterrows():
            expected = parse_entities(sample["expected_entities"])
            transcript = str(sample["transcript"])
            row = {
                "sample_id": sample.get("sample_id", ""),
                "strategy": strategy_name,
                "model": args.model,
                "transcript": transcript,
                "expected_entities": json.dumps(expected, ensure_ascii=False, sort_keys=True),
                "predicted_entities": "",
                "status": "ok",
                "error": "",
            }

            start = time.perf_counter()
            try:
                predicted_result = strategy.extract(transcript)
                duration = time.perf_counter() - start
                predicted = predicted_result.model_dump()
                metrics = compare_entities(expected, predicted)

                row.update({
                    "predicted_entities": json.dumps(predicted, ensure_ascii=False, sort_keys=True),
                    "duration_seconds": round(duration, 4),
                    **flatten_metrics(metrics),
                })
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
    parser = argparse.ArgumentParser(description="Run NER evaluation on reference transcripts.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--strategies", nargs="+", default=["chained", "split"])
    parser.add_argument("--model", default="openai/gpt-4o")
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(f"NER eval input file does not exist: {args.input}")

    rows = run_eval(args)
    write_results(rows, args.output)

    print(f"Wrote NER eval results: {args.output}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main()
