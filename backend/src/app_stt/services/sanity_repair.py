import json
import os
import re

import requests

from app_stt.services.sanity_llm import llm_api_config

try:
    from logging_config import logger
except ModuleNotFoundError:  # poza Django logger schodzi do stdlib
    import logging
    logger = logging.getLogger("sanity_repair")


REPAIR_SCOPES = {
    "patient_data": {"name", "age", "pesel"},
    "description": {"organ", "description"},
    "all": {"name", "organ", "age", "pesel", "description"},
}

FORM_FIELDS = tuple(sorted(REPAIR_SCOPES["all"]))


def empty_repair(scope: str, reason: str, ran: bool = False) -> dict:
    return {
        "ran": ran,
        "reason": reason,
        "scope": scope,
        "applied": False,
        "change_count": 0,
        "changed_fields": [],
        "changes": [],
        "repaired_form_data": None,
    }


def validate_repair_scope(repair_scope: str) -> None:
    if repair_scope not in REPAIR_SCOPES:
        raise ValueError(
            f"Unknown repair scope '{repair_scope}'. "
            f"Supported: {', '.join(sorted(REPAIR_SCOPES))}."
        )


def repair_with_llm(transcript: str, form_data: dict, rule_issues: list, repair_scope: str = "all") -> dict:
    """Ask an LLM for scoped form repair. The caller decides whether to apply it."""
    validate_repair_scope(repair_scope)

    api_key, url = llm_api_config()
    if not api_key:
        return empty_repair(repair_scope, "no_api_key")

    allowed_fields = sorted(REPAIR_SCOPES[repair_scope])
    model = os.getenv("SANITY_LLM_MODEL", "gpt-4o-2024-05-13")
    prompt = _build_repair_prompt(
        transcript,
        _scoped_form_data(form_data, allowed_fields),
        _scoped_rule_issues(rule_issues, set(allowed_fields)),
        allowed_fields,
    )

    try:
        response = requests.post(
            url=url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
            }),
            timeout=30,
        )
        if response.status_code != 200:
            logger.warning(f"[SANITY_CHECK] LLM repair HTTP {response.status_code}")
            return empty_repair(repair_scope, "http_error", ran=True)

        reply = response.json()["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(_clean_json_reply(reply))
        except json.JSONDecodeError:
            logger.warning("[SANITY_CHECK] LLM repair returned non-JSON output")
            return empty_repair(repair_scope, "parse_error", ran=True)

        if not isinstance(parsed, dict):
            return empty_repair(repair_scope, "parse_error", ran=True)

        repaired_form_data, changes = validated_repaired_form_data(
            form_data,
            parsed,
            repair_scope,
            transcript,
        )
        if repaired_form_data is None:
            return empty_repair(repair_scope, "parse_error", ran=True)

        return {
            "ran": True,
            "reason": "ok",
            "scope": repair_scope,
            "applied": bool(changes),
            "change_count": len(changes),
            "changed_fields": [change["field"] for change in changes],
            "changes": changes,
            "repaired_form_data": repaired_form_data if changes else None,
        }
    except Exception as exc:
        logger.warning(f"[SANITY_CHECK] LLM repair failed: {exc}")
        return empty_repair(repair_scope, "exception", ran=True)


def validated_repaired_form_data(
    original_form_data: dict,
    parsed: dict,
    scope: str,
    transcript: str = "",
) -> tuple[dict | None, list[dict]]:
    validate_repair_scope(scope)

    proposed = parsed.get("repaired_form_data")
    if not isinstance(proposed, dict):
        return None, []

    allowed_fields = REPAIR_SCOPES[scope]
    repaired = {
        field: _normalize_form_value(original_form_data.get(field, ""))
        for field in FORM_FIELDS
    }
    for field in allowed_fields:
        if field not in proposed:
            continue
        proposed_value = _normalize_form_value(proposed[field])
        if not _is_allowed_repair_value(field, proposed_value, transcript):
            continue
        repaired[field] = proposed_value

    changes = _build_repair_changes(
        original_form_data,
        repaired,
        parsed.get("changes", []),
        allowed_fields,
    )
    return repaired, changes


def _build_repair_prompt(transcript: str, form_data: dict, rule_issues: list, allowed_fields: list[str]) -> str:
    return f"""
    You repair a pathology form filled from a speech transcript.

    Return only JSON with this shape:
    {{
      "repaired_form_data": {{
        "field_from_allowed_list": "..."
      }},
      "changes": [
        {{"field": "organ", "before": "", "after": "tarczyca", "reason": "Organ appears in transcript."}}
      ]
    }}

    Rules:
    - form_data contains only fields you may change.
    - Return repaired_form_data with only allowed fields.
    - Do not diagnose.
    - Do not add facts that are not present in the transcript.
    - If uncertain, leave a field unchanged.
    - You may change only these fields: {", ".join(allowed_fields)}.
    - PESEL may be changed only if the full number is explicitly present in the transcript.
    - Age may be changed only if it is explicitly present or can be computed from PESEL.
    - Description may be cleaned linguistically, but must not add medical facts.

    transcript:
    {transcript}

    form_data:
    {json.dumps(form_data, ensure_ascii=False)}

    rule_issues:
    {json.dumps(rule_issues, ensure_ascii=False)}
    """


def _scoped_form_data(form_data: dict, allowed_fields: list[str]) -> dict:
    return {field: form_data.get(field, "") for field in allowed_fields}


def _scoped_rule_issues(rule_issues: list, allowed_fields: set[str]) -> list[dict]:
    scoped_issues = []
    for issue in rule_issues:
        if not isinstance(issue, dict) or issue.get("field") not in allowed_fields:
            continue
        scoped_issues.append({
            key: issue[key]
            for key in ("severity", "source", "code", "field", "message")
            if key in issue
        })
    return scoped_issues


def _clean_json_reply(reply: str) -> str:
    return reply.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()


def _normalize_form_value(value) -> str:
    if value is None:
        return ""
    return str(value)


def _is_allowed_repair_value(field: str, value: str, transcript: str) -> bool:
    if field == "pesel":
        digits = re.sub(r"\D", "", value)
        if digits != value or len(digits) != 11:
            return False
        return digits in re.sub(r"\D", "", transcript or "")

    if field == "age":
        stripped = value.strip()
        if not stripped:
            return True
        if not stripped.isdigit():
            return False
        return 0 <= int(stripped) <= 120

    return True


def _build_repair_changes(
    original_form_data: dict,
    repaired_form_data: dict,
    llm_changes: list,
    allowed_fields: set[str],
) -> list[dict]:
    reasons = {}
    if isinstance(llm_changes, list):
        for change in llm_changes:
            if isinstance(change, dict) and change.get("field") in allowed_fields:
                reasons[str(change["field"])] = str(change.get("reason") or "")

    changes = []
    for field in sorted(allowed_fields):
        before = _normalize_form_value(original_form_data.get(field, ""))
        after = _normalize_form_value(repaired_form_data.get(field, ""))
        if before == after:
            continue
        changes.append({
            "field": field,
            "before": before,
            "after": after,
            "reason": reasons.get(field, "LLM repair changed this field."),
        })
    return changes
