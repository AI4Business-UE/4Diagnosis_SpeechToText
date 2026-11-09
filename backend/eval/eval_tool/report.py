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
    "Tekst referencyjny",
    "Surowy transkrypt",
    "Skorygowany transkrypt",
    "Wynik NER (JSON)",
    "Status sędziego LLM",
    "Wynik sędziego LLM (0–4)",
    "Uzasadnienie sędziego LLM",
    "Pominięcia sędziego LLM",
    "Dodatki sędziego LLM",
    "Sprzeczności sędziego LLM",
    "Powód pominięcia sędziego",
)
_REVIEW_STATUS_LABELS = {
    "complete": "kompletna",
    "incomplete": "niekompletna",
    "failed": "nieudana",
}
_JUDGE_STATUS_LABELS = {
    "judged": "oceniono",
    "opted_out": "pominięto na poziomie próbki",
    "disabled": "sędzia wyłączony globalnie",
    "error": "błąd oceny sędziego",
    "not_run": "nie oceniono — błąd pipeline'u",
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
            row.get("reference_text"),
            row.get("transcript"),
            row.get("corrected_transcript"),
            _json_cell(row.get("entities")),
            _JUDGE_STATUS_LABELS.get(row.get("judge_status"), row.get("judge_status")),
            row.get("judge_score"),
            row.get("judge_rationale"),
            _line_cell(row.get("judge_omissions")),
            _line_cell(row.get("judge_additions")),
            _line_cell(row.get("judge_contradictions")),
            row.get("judge_opt_out_reason"),
        ]
        if include_ner_reference:
            values.append(_json_cell(row.get("ner_reference")))
        sheet.append(values)

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path


def _json_cell(value: Any) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False)


def _line_cell(value: Any) -> str | None:
    if not value:
        return None
    return "\n".join(str(item) for item in value)
