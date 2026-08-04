import json
from datetime import datetime
from pathlib import Path
from typing import Any


SANITY_LOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "sanity_logs"
    / "runtime_sanity.jsonl"
)


def _sanitize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    """Keep runtime QA logs useful without storing patient/form payloads."""
    allowed = ("severity", "source", "code", "field", "message")
    return {key: issue[key] for key in allowed if key in issue}


def build_sanity_record(sanity_result: dict[str, Any]) -> dict[str, Any]:
    issues = [
        _sanitize_issue(issue)
        for issue in sanity_result.get("issues", [])
        if isinstance(issue, dict)
    ]
    metrics = sanity_result.get("metrics", {})

    return {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": sanity_result.get("status", ""),
        "score": sanity_result.get("score", ""),
        "issue_count": len(issues),
        "issue_codes": sorted({
            str(issue.get("code", ""))
            for issue in issues
            if issue.get("code")
        }),
        "issue_fields": sorted({
            str(issue.get("field", ""))
            for issue in issues
            if issue.get("field")
        }),
        "issues": issues,
        "transcript_length": metrics.get("transcript_length", 0),
        "description_length": metrics.get("description_length", 0),
    }


def append_sanity_record(
    sanity_result: dict[str, Any],
    log_path: Path | str = SANITY_LOG_PATH,
) -> dict[str, Any]:
    record = build_sanity_record(sanity_result)
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record
