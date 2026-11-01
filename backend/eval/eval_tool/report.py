from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import Workbook


_REVIEW_HEADERS = (
    "Identyfikator próbki",
    "Status",
    "Surowy transkrypt",
    "Wynik NER (JSON)",
    "Skorygowany transkrypt",
)
_REVIEW_STATUS_LABELS = {
    "complete": "kompletna",
    "incomplete": "niekompletna",
    "failed": "nieudana",
}

def default_report_path(eval_dir: str | Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return Path(eval_dir) / "results" / f"evaluation_{timestamp}.json"


def default_review_workbook_path(eval_dir: str | Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return Path(eval_dir) / "results" / f"ner_review_{timestamp}.xlsx"


def save_report(
    report: dict[str, Any],
    output_path: str | Path,
    *,
    include_details: bool = False,
) -> Path:
    """Persist a JSON report, excluding clinical per-sample details by default."""
    path = Path(output_path)
    if path.exists():
        raise FileExistsError(f"Raport już istnieje; nie nadpisano pliku: {path}")
    content = copy.deepcopy(report)
    content.pop("review_rows", None)
    if not include_details:
        content.pop("details", None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def save_review_workbook(
    review_rows: list[dict[str, Any]],
    output_path: str | Path,
    *,
    include_ner_reference: bool = False,
) -> Path:
    """Save per-sample clinical outputs in a local, human-review workbook."""
    path = Path(output_path)
    if path.exists():
        raise FileExistsError(f"Arkusz przeglądu już istnieje; nie nadpisano pliku: {path}")

    headers = _REVIEW_HEADERS + (("Referencja Gold NER (JSON)",) if include_ner_reference else ())
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Przegląd NER"
    sheet.append(headers)
    for row in review_rows:
        values: list[Any] = [
            row.get("sample_id"),
            _REVIEW_STATUS_LABELS.get(row.get("status"), row.get("status")),
            row.get("transcript"),
            _json_cell(row.get("entities")),
            row.get("corrected_transcript"),
        ]
        if include_ner_reference:
            values.append(_json_cell(row.get("ner_reference")))
        sheet.append(values)

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path


def _json_cell(value: Any) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False)
