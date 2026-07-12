import re
import requests
import json
import os
from logging_config import logger

def run_data_sanity_check(transcript: str, form_data: dict) -> dict:
    issues = []

    issues += check_required_fields(form_data)
    issues += check_pesel(form_data)
    issues += check_age(form_data)
    issues += check_dimensions(transcript, form_data)
    issues += check_description_consistency(transcript, form_data)

    if issues:
        issues += check_with_llm(transcript, form_data, issues)

    score = calculate_score(issues)

    return {
        "status": "ok" if not issues else "suspicious",
        "score": score,
        "issues": issues,
        "metrics": {
            "transcript_length": len(transcript or ""),
            "description_length": len(str(form_data.get("description", "") or "")),
        },
    }


def check_required_fields(form_data: dict) -> list:
    issues = []

    required_fields = ["organ", "name", "age", "pesel", "description"]

    for field in required_fields:
        value = form_data.get(field)

        if not str(value or "").strip():
            issues.append({
                "severity": "warning",
                "source": "rules",
                "code": "missing_required_field",
                "field": field,
                "message": f"Missing required field: {field}",
            })
    return issues

def check_pesel(form_data: dict) -> list:
    issues = []

    pesel = str(form_data.get("pesel", "")).strip()

    if not pesel:
        return issues

    if len(pesel) != 11:
        issues.append({
            "severity": "warning",
            "source": "rules",
            "code": "invalid_pesel_length",
            "field": "pesel",
            "message": "PESEL should have exactly 11 digits.",
        })
        return issues

    if not pesel.isdigit():
        issues.append({
            "severity": "warning",
            "source": "rules",
            "code": "invalid_pesel_format",
            "field": "pesel",
            "message": "PESEL should contain only digits.",
        })
        return issues

    weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
    digits = [int(char) for char in pesel]
    total = sum(digits[i] * weights[i] for i in range(10))
    check_sum = (10 - (total % 10)) % 10

    if check_sum != digits[10]:
        issues.append({
            "severity": "warning",
            "source": "rules",
            "code": "invalid_pesel_checksum",
            "field": "pesel",
            "message": "PESEL checksum is invalid.",
        })

    return issues

def check_age(form_data: dict) -> list:
    issues = []

    age = str(form_data.get("age", "")).strip()

    if not age:
        return issues

    if not age.isdigit():
        issues.append({
            "severity": "warning",
            "source": "rules",
            "code": "age_not_a_number",
            "field": "age",
            "message": "Age is not a number.",
        })
        return issues

    age_number = int(age)

    if age_number > 120:
        issues.append({
            "severity": "warning",
            "source": "rules",
            "code": "age_too_high",
            "field": "age",
            "message": "Age is too high.",
        })

    if age_number < 0:
        issues.append({
            "severity": "warning",
            "source": "rules",
            "code": "negative_age",
            "field": "age",
            "message": "Age is a negative number.",
        })

    return issues

def _to_cm(value: float, unit: str) -> float | None:
    unit = unit.lower()

    if unit == "mm":
        return value / 10

    if unit == "cm":
        return value

    if unit in ["m", "metr", "metry", "metrów", "metra"]:
        return value * 100

    return None

DIMENSION_PATTERN = r"(\d+(?:[,.]\d+)?)\s*(mm|cm|metrów|metry|metra|metr|m)"

def check_dimensions(transcript: str, form_data: dict) -> list:
    issues = []
    seen_issues = set()

    def add_issue(issue: dict):
        key = (issue.get("code"), issue.get("evidence"))
        if key in seen_issues:
            return
        seen_issues.add(key)
        issues.append(issue)

    description = form_data.get("description", "")
    text = f"{description} {transcript or ''}".lower()

    matches = re.findall(DIMENSION_PATTERN, text)

    for raw_value, raw_unit in matches:
        value = float(raw_value.replace(",", "."))
        unit = raw_unit.lower()
        value_cm = _to_cm(value, unit)

        evidence = f"{raw_value} {raw_unit}"

        if value <= 0:
            add_issue({
                "severity": "error",
                "source": "rules",
                "code": "non_positive_dimension",
                "field": "description",
                "message": "Dimension is zero or negative.",
                "evidence": evidence,
            })

        if unit in ["m", "metr", "metry", "metrów", "metra"]:
            add_issue({
                "severity": "warning",
                "source": "rules",
                "code": "suspicious_unit_meter",
                "field": "description",
                "message": "Suspicious unit: meters used in tissue description.",
                "evidence": evidence,
            })

        if value_cm > 50:
            add_issue({
                "severity": "warning",
                "source": "rules",
                "code": "suspicious_large_dimension",
                "field": "description",
                "message": "Suspiciously large dimension detected.",
                "evidence": evidence,
            })

    return issues

LESION_WORDS = ["guz", "guza", "guzem", "torbiel", "torbieli", "polip", "polipa", "ognisko", "zmiana", "zmiany"]

def check_description_consistency(transcript: str, form_data: dict) -> list:
    issues = []

    description = str(form_data.get("description", "") or "").lower()
    transcript_text = str(transcript or "").lower()

    has_lesion_in_description = any(word in description for word in LESION_WORDS)
    has_lesion_in_transcript = any(word in transcript_text for word in LESION_WORDS)

    has_dimension_in_description = re.search(DIMENSION_PATTERN, description) is not None

    if has_lesion_in_description and not has_dimension_in_description:
        issues.append({
            "severity": "warning",
            "source": "rules",
            "code": "lesion_without_dimension",
            "field": "description",
            "message": "Description mentions a lesion but does not include any dimension.",
        })

    if has_lesion_in_transcript and not has_lesion_in_description:
        issues.append({
            "severity": "warning",
            "source": "rules",
            "code": "possible_lesion_omitted",
            "field": "description",
            "message": "Transcript mentions a lesion, but the filled description may omit it.",
        })

    return issues

def calculate_score(issues: list) -> float:
    score = 1.0

    penalties = {
        "error": 0.4,
        "warning": 0.2,
        "info": 0.05,
    }

    for issue in issues:
        severity = issue.get("severity", "warning")
        score -= penalties.get(severity, 0.2)

    return max(score, 0.0)


def check_with_llm(transcript: str, form_data: dict, rule_issues: list) -> list:
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_KEY")

    if not api_key:
        return []

    prompt = f"""
    You are reviewing a pathology form filled by an LLM from a speech transcript.

    Compare the original transcript, form_data and existing rule issues.
    Check whether patient data and the macro-description look consistent and sensible.
    Do not correct the form.
    Do not diagnose.
    Return only JSON in this format:
    {{"issues": []}}

    Each issue must have:
    severity, source, code, field, message, evidence.

    source must always be "llm_review".

    transcript:
    {transcript}

    form_data:
    {json.dumps(form_data, ensure_ascii=False)}

    rule_issues:
    {json.dumps(rule_issues, ensure_ascii=False)}
    """

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": "gpt-4o-2024-05-13",
                "messages": [
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
            }),
            timeout=20,
        )

        if response.status_code != 200:
            return []

        reply = response.json()["choices"][0]["message"]["content"]
        cleaned = reply.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)

        llm_issues = parsed.get("issues", [])
        if not isinstance(llm_issues, list):
            return []

        normalized_issues = []
        for issue in llm_issues:
            if not isinstance(issue, dict):
                continue

            normalized_issue = {
                "severity": issue.get("severity", "warning"),
                "source": "llm_review",
                "code": issue.get("code", "llm_review_issue"),
                "field": issue.get("field", "description"),
                "message": issue.get("message", "LLM review found a possible issue."),
            }

            if issue.get("evidence"):
                normalized_issue["evidence"] = issue["evidence"]

            normalized_issues.append(normalized_issue)

        return normalized_issues

    except Exception as exc:
        logger.warning(f"[SANITY_CHECK] LLM review failed: {exc}")
        return []
