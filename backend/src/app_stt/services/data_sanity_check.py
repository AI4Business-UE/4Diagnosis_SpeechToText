import re
import requests
import json
import os

try:
    from logging_config import logger
except ModuleNotFoundError:  # pozwala uruchomić self-check standalone (bez ścieżki Django)
    import logging
    logger = logging.getLogger("data_sanity_check")


ALLOWED_SEVERITIES = {"error", "warning", "info"}

# Domyślne wagi per severity (fallback, gdy kod issue nie ma własnej wagi).
SEVERITY_WEIGHTS = {
    "error": 0.4,
    "warning": 0.15,
    "info": 0.03,
}

# Wagi per konkretny kod issue — pozwalają różnicować „lekko podejrzany” od „katastrofy”.
CODE_WEIGHTS = {
    "missing_required_field": 0.08,
    "invalid_pesel_length": 0.25,
    "invalid_pesel_format": 0.25,
    "invalid_pesel_checksum": 0.3,
    "age_not_a_number": 0.2,
    "age_too_high": 0.2,
    "negative_age": 0.3,
    "non_positive_dimension": 0.5,
    "suspicious_unit_meter": 0.15,
    "suspicious_large_dimension": 0.15,
    "lesion_without_dimension": 0.1,
    "possible_lesion_omitted": 0.15,
}


def _llm_force_enabled() -> bool:
    """LLM-review domyślnie odpala się tylko gdy reguły coś znalazły (oszczędność kosztu).
    SANITY_LLM_FORCE=1 wymusza uruchomienie także na formularzach czystych wg reguł."""
    return str(os.getenv("SANITY_LLM_FORCE", "")).strip().lower() in {"1", "true", "yes", "on"}


def run_data_sanity_check(transcript: str, form_data: dict) -> dict:
    issues = []

    issues += check_required_fields(form_data)
    issues += check_pesel(form_data)
    issues += check_age(form_data)
    issues += check_dimensions(transcript, form_data)
    issues += check_description_consistency(transcript, form_data)

    llm = {"ran": False, "issues": [], "reason": "disabled"}
    if issues or _llm_force_enabled():
        llm = check_with_llm(transcript, form_data, issues)
        issues += llm["issues"]

    return {
        "status": derive_status(issues),
        "score": calculate_score(issues),
        "issues": issues,
        "llm_review": {
            "ran": llm["ran"],
            "reason": llm["reason"],
            "issue_count": len(llm["issues"]),
        },
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

# \b po jednostce, żeby "20 ml" nie było czytane jako "20 m" (metry).
DIMENSION_PATTERN = r"(\d+(?:[,.]\d+)?)\s*(mm|cm|metrów|metry|metra|metr|m)\b"

def check_dimensions(transcript: str, form_data: dict) -> list:
    """Skanuje wymiary osobno w opisie i w transkrypcji, żeby `field` w issue
    wiernie mówił, skąd pochodzi wartość. Wymiar obecny w obu miejscach jest
    raportowany raz — przypisany do `description`."""
    issues = []
    seen = set()  # (field, code, evidence)
    described_evidence = set()

    def scan(text: str, field: str) -> None:
        for raw_value, raw_unit in re.findall(DIMENSION_PATTERN, str(text or "").lower()):
            evidence = f"{raw_value} {raw_unit}"

            # Wymiar już zgłoszony z opisu — nie duplikuj go z transkrypcji.
            if field == "transcript" and evidence in described_evidence:
                continue

            value = float(raw_value.replace(",", "."))
            unit = raw_unit.lower()
            value_cm = _to_cm(value, unit)

            if field == "description":
                described_evidence.add(evidence)

            def add_issue(severity: str, code: str, message: str) -> None:
                key = (field, code, evidence)
                if key in seen:
                    return
                seen.add(key)
                issues.append({
                    "severity": severity,
                    "source": "rules",
                    "code": code,
                    "field": field,
                    "message": message,
                    "evidence": evidence,
                })

            if value <= 0:
                add_issue("error", "non_positive_dimension", "Dimension is zero or negative.")

            if unit in ["m", "metr", "metry", "metrów", "metra"]:
                add_issue("warning", "suspicious_unit_meter", "Suspicious unit: meters used in tissue description.")

            if value_cm is not None and value_cm > 50:
                add_issue("warning", "suspicious_large_dimension", "Suspiciously large dimension detected.")

    scan(form_data.get("description", ""), "description")
    scan(transcript, "transcript")

    return issues

LESION_WORDS = ["guz", "guza", "guzem", "torbiel", "torbieli", "polip", "polipa", "ognisko", "zmiana", "zmiany"]
# Dopasowanie z granicami słów — inaczej "guz" łapałoby np. "guzik".
LESION_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(word) for word in LESION_WORDS) + r")\b")

def check_description_consistency(transcript: str, form_data: dict) -> list:
    issues = []

    description = str(form_data.get("description", "") or "").lower()
    transcript_text = str(transcript or "").lower()

    has_lesion_in_description = LESION_PATTERN.search(description) is not None
    has_lesion_in_transcript = LESION_PATTERN.search(transcript_text) is not None

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

def _issue_weight(issue: dict) -> float:
    code = issue.get("code")
    if code in CODE_WEIGHTS:
        return CODE_WEIGHTS[code]
    severity = issue.get("severity", "warning")
    return SEVERITY_WEIGHTS.get(severity, SEVERITY_WEIGHTS["warning"])

def calculate_score(issues: list) -> float:
    """Multiplikatywny score w (0, 1]. Każde issue mnoży wynik przez (1 - waga),
    więc kilka drobnych warningów nie „zeruje” od razu, a błąd krytyczny ciągnie mocniej."""
    score = 1.0
    for issue in issues:
        score *= (1 - _issue_weight(issue))
    return round(max(score, 0.0), 4)

def derive_status(issues: list) -> str:
    """Trzy poziomy wyprowadzone z severity: brak issue -> ok, dowolny error -> critical,
    inaczej warning."""
    if not issues:
        return "ok"
    if any(issue.get("severity") == "error" for issue in issues):
        return "critical"
    return "warning"


def check_with_llm(transcript: str, form_data: dict, rule_issues: list) -> dict:
    """Zwraca {"ran": bool, "issues": list, "reason": str}.
    `ran=False` oznacza, że LLM realnie się nie wykonał (brak klucza / błąd sieci)."""
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_KEY")

    if not api_key:
        return {"ran": False, "issues": [], "reason": "no_api_key"}

    model = os.getenv("SANITY_LLM_MODEL", "gpt-4o-2024-05-13")

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
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
            }),
            timeout=20,
        )

        if response.status_code != 200:
            logger.warning(f"[SANITY_CHECK] LLM review HTTP {response.status_code}")
            return {"ran": False, "issues": [], "reason": "http_error"}

        reply = response.json()["choices"][0]["message"]["content"]
        cleaned = reply.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("[SANITY_CHECK] LLM review returned non-JSON output")
            return {"ran": True, "issues": [], "reason": "parse_error"}

        llm_issues = parsed.get("issues", [])
        if not isinstance(llm_issues, list):
            return {"ran": True, "issues": [], "reason": "parse_error"}

        normalized_issues = []
        for issue in llm_issues:
            if not isinstance(issue, dict):
                continue

            severity = issue.get("severity", "warning")
            if severity not in ALLOWED_SEVERITIES:
                severity = "warning"

            normalized_issue = {
                "severity": severity,
                "source": "llm_review",
                "code": issue.get("code", "llm_review_issue"),
                "field": issue.get("field", "description"),
                "message": issue.get("message", "LLM review found a possible issue."),
            }

            if issue.get("evidence"):
                normalized_issue["evidence"] = issue["evidence"]

            normalized_issues.append(normalized_issue)

        return {"ran": True, "issues": normalized_issues, "reason": "ok"}

    except Exception as exc:
        logger.warning(f"[SANITY_CHECK] LLM review failed: {exc}")
        return {"ran": False, "issues": [], "reason": "exception"}


def _self_check() -> None:
    # Zdejmij klucze, żeby self-check nigdy nie chodził do sieci.
    saved_keys = {
        name: os.environ.pop(name, None)
        for name in ("OPENROUTER_API_KEY", "OPENAI_KEY", "SANITY_LLM_FORCE")
    }
    try:
        # Score multiplikatywny: 5 drobnych warningów nie zeruje wyniku...
        five_warnings = [{"severity": "warning", "code": "missing_required_field"} for _ in range(5)]
        score_five = calculate_score(five_warnings)
        assert 0.0 < score_five < 1.0
        # ...i jest wyżej (lepiej) niż pojedynczy twardy błąd.
        assert score_five > calculate_score([{"severity": "error", "code": "non_positive_dimension"}])

        # Status trójpoziomowy z severity.
        assert derive_status([]) == "ok"
        assert derive_status([{"severity": "warning", "code": "x"}]) == "warning"
        assert derive_status([{"severity": "error", "code": "x"}]) == "critical"

        # Provenance: wymiar tylko w transkrypcji -> field=transcript.
        only_transcript = check_dimensions("guz 60 cm", {"description": ""})
        assert any(issue["field"] == "transcript" for issue in only_transcript)
        # Wymiar tylko w opisie -> field=description.
        only_description = check_dimensions("", {"description": "guz 60 cm"})
        assert any(issue["field"] == "description" for issue in only_description)
        # Wymiar w obu -> raportowany raz, z description.
        both = check_dimensions("guz 60 cm", {"description": "guz 60 cm"})
        large = [issue for issue in both if issue["code"] == "suspicious_large_dimension"]
        assert len(large) == 1 and large[0]["field"] == "description"

        # Granice słów: "guz" łapie zmianę, ale nie "guzik".
        assert LESION_PATTERN.search("guz") is not None
        assert LESION_PATTERN.search("guzik") is None

        # "20 ml" to objętość, nie wymiar w metrach — nie może dawać issue wymiarowego.
        assert check_dimensions("BAL 20 ml", {"description": "materiał 20 ml"}) == []
        # "20 cm" nadal jest wykrywane.
        assert check_dimensions("", {"description": "guz 60 cm"}) != []

        # Bez klucza LLM realnie się nie uruchamia.
        llm = check_with_llm("x", {}, [])
        assert llm["ran"] is False and llm["reason"] == "no_api_key"

        # Pełny wynik ma blok llm_review i nie chodzi do sieci bez klucza.
        result = run_data_sanity_check("guz 3 cm", {
            "organ": "", "name": "", "age": "", "pesel": "", "description": "",
        })
        assert result["llm_review"]["ran"] is False
        assert result["status"] in {"ok", "warning", "critical"}
    finally:
        for name, value in saved_keys.items():
            if value is not None:
                os.environ[name] = value


if __name__ == "__main__":
    _self_check()
    print("Data sanity check self-check passed")
