from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_report_path(eval_dir: str | Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return Path(eval_dir) / "results" / f"evaluation_{timestamp}.json"


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
    if not include_details:
        content.pop("details", None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
