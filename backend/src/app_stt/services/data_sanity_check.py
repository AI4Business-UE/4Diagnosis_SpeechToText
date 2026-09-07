import re
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app_stt.services.sanity_llm import llm_api_config
from app_stt.data.sanity_terms import (
    LESION_WORDS,
    REQUIRED_FORM_FIELDS,
    SANITY_ALLOWED_SEVERITIES,
)
from app_stt.data.organ_plausibility import (
    ORGAN_MAX_DIMENSION_CM,
    GLOBAL_MAX_DIMENSION_CM,
    ORGAN_STEMS,
)
from app_stt.services.sanity_repair import (
    empty_repair,
    repair_with_llm,
    validate_repair_scope,
    validated_repaired_form_data,
)

try:
    from logging_config import logger
except ModuleNotFoundError:  # poza Django logger schodzi do stdlib
    import logging
    logger = logging.getLogger("data_sanity_check")

SANITY_MODES = {"rules", "rules_and_llm", "review_and_repair"}


def _resolve_organ(form_data: dict) -> str | None:
    """Rozpoznaje kanoniczną nazwę narządu z pola `organ` (obsługa polskiej fleksji
    przez dopasowanie rdzenia). Pierwszy pasujący rdzeń wygrywa (kolejność w ORGAN_STEMS)."""
    text = str(form_data.get("organ") or "").lower().strip()
    if not text:
        return None
    for stem, canonical in ORGAN_STEMS:
        if stem in text:
            return canonical
    return None


# Domyślne wagi per severity (fallback, gdy kod issue nie ma własnej wagi).
SEVERITY_WEIGHTS = {
    "error": 0.4,
    "warning": 0.15,
    "info": 0.03,
}

# Wagi per konkretny kod issue — pozwalają różnicować „lekko podejrzany” od „katastrofy”.
CODE_WEIGHTS = {
    "missing_required_field": 0.12,
    "invalid_pesel_length": 0.25,
    "invalid_pesel_format": 0.25,
    "invalid_pesel_checksum": 0.3,
    "invalid_pesel_date": 0.3,
    "age_not_a_number": 0.2,
    "age_too_high": 0.2,
    "negative_age": 0.3,
    "age_pesel_mismatch": 0.25,
    "description_not_meaningful": 0.15,
    "non_positive_dimension": 0.5,
    "suspicious_unit_meter": 0.25,
    "suspicious_large_dimension": 0.3,
    "implausible_dimension_for_organ": 0.25,
    "lesion_without_dimension": 0.12,
    "possible_lesion_omitted": 0.2,
}


def run_data_sanity_check(
    transcript: str,
    form_data: dict,
    mode: str = "rules",
    repair_scope: str = "all",
) -> dict:
    """Run sanity QA in a selected mode.

    Default `rules` is deterministic and never uses the network. `rules_and_llm`
    adds an opt-in LLM review for eval experiments. `review_and_repair` asks an
    LLM for a scoped form repair and re-runs rules on the repaired form.
    """
    if mode not in SANITY_MODES:
        raise ValueError(f"Unknown sanity mode '{mode}'. Supported: {', '.join(sorted(SANITY_MODES))}.")
    if mode == "review_and_repair":
        validate_repair_scope(repair_scope)

    original_issues = run_rules(transcript, form_data)
    issues = list(original_issues)
    llm = {"ran": False, "issues": [], "reason": "mode_rules"}
    repair = empty_repair(repair_scope, f"mode_{mode}")

    if mode == "rules_and_llm":
        llm = check_with_llm(transcript, form_data, issues)
        issues += llm["issues"]
    elif mode == "review_and_repair":
        llm = {"ran": False, "issues": [], "reason": "mode_review_and_repair"}
        repair = repair_with_llm(transcript, form_data, original_issues, repair_scope)
        if repair["applied"] and repair["repaired_form_data"] is not None:
            issues = run_rules(transcript, repair["repaired_form_data"])

    status = derive_status(issues)
    score = calculate_score(issues)
    final_form_data = repair["repaired_form_data"] if repair["applied"] and repair["repaired_form_data"] is not None else form_data

    return {
        "status": status,
        "score": score,
        "issues": issues,
        "issue_count": len(issues),
        "original_status": derive_status(original_issues),
        "original_score": calculate_score(original_issues),
        "original_issue_count": len(original_issues),
        "llm_review": {
            "ran": llm["ran"],
            "reason": llm["reason"],
            "issue_count": len(llm["issues"]),
        },
        "repair": repair,
        "metrics": {
            "transcript_length": len(transcript or ""),
            "description_length": len(str(final_form_data.get("description", "") or "")),
        },
    }


def run_rules(transcript: str, form_data: dict) -> list:
    issues = []
    issues += check_required_fields(form_data)
    issues += check_description_quality(form_data)
    issues += check_pesel(form_data)
    issues += check_age(form_data)
    issues += check_age_pesel_consistency(form_data)
    issues += check_dimensions(transcript, form_data)
    issues += check_description_consistency(transcript, form_data)
    return issues


def check_required_fields(form_data: dict) -> list:
    issues = []

    for field in REQUIRED_FORM_FIELDS:
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

def check_description_quality(form_data: dict) -> list:
    """Opis może być technicznie niepusty, ale bez treści (sama interpunkcja/liczba, np. "."
    lub "3 cm"). Sam whitespace łapie już check_required_fields, więc tu go nie dublujemy."""
    description = str(form_data.get("description", "") or "").strip()

    if not description:
        return []

    letters = re.sub(r"[^a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]", "", description)
    if len(letters) < 3:
        return [{
            "severity": "warning",
            "source": "rules",
            "code": "description_not_meaningful",
            "field": "description",
            "message": "Description present but lacks meaningful text content.",
        }]

    return []

_PESEL_CENTURY = {0: 1900, 20: 2000, 40: 2100, 60: 2200, 80: 1800}


def _pesel_birth_date(pesel: str) -> datetime | None:
    """Dekoduje datę urodzenia z PESEL-a albo None, gdy data jest niemożliwa. Obsługuje wszystkie
    zakresy stuleci (miesiąc +0/+20/+40/+60/+80 → 1900/2000/2100/2200/1800)."""
    pesel = str(pesel or "").strip()
    if len(pesel) != 11 or not pesel.isdigit():
        return None

    year = int(pesel[0:2])
    month_raw = int(pesel[2:4])
    day = int(pesel[4:6])

    century = _PESEL_CENTURY.get((month_raw // 20) * 20)
    month = month_raw % 20
    if century is None or not (1 <= month <= 12):
        return None

    try:
        return datetime(century + year, month, day)
    except ValueError:
        return None


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

    # Poprawna checksuma nie gwarantuje realnej daty — łapiemy daty niemożliwe i z przyszłości.
    birth = _pesel_birth_date(pesel)
    if birth is None:
        issues.append({
            "severity": "warning",
            "source": "rules",
            "code": "invalid_pesel_date",
            "field": "pesel",
            "message": "PESEL encodes a non-existent date.",
        })
    elif birth > datetime.today():
        issues.append({
            "severity": "warning",
            "source": "rules",
            "code": "invalid_pesel_date",
            "field": "pesel",
            "message": "PESEL encodes a future birth date.",
        })

    return issues

def check_age(form_data: dict) -> list:
    issues = []

    age = str(form_data.get("age", "")).strip()

    if not age:
        return issues

    try:
        age_number = int(age)
    except ValueError:
        issues.append({
            "severity": "warning",
            "source": "rules",
            "code": "age_not_a_number",
            "field": "age",
            "message": "Age is not a number.",
        })
        return issues

    if age_number < 0:
        issues.append({
            "severity": "warning",
            "source": "rules",
            "code": "negative_age",
            "field": "age",
            "message": "Age is a negative number.",
        })

    if age_number > 120:
        issues.append({
            "severity": "warning",
            "source": "rules",
            "code": "age_too_high",
            "field": "age",
            "message": "Age is too high.",
        })

    return issues

def _age_from_pesel(pesel: str) -> int | None:
    """Wiek z daty urodzenia zakodowanej w PESEL-u. Zwraca None gdy PESEL/data są niepoprawne."""
    birth_date = _pesel_birth_date(pesel)
    if birth_date is None:
        return None

    today = datetime.today()
    if birth_date > today:
        return None
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )

def check_age_pesel_consistency(form_data: dict) -> list:
    """Rozjazd między polem `age` a wiekiem wyliczonym z PESEL-a to realny sygnał błędu
    (w produkcji wiek jest liczony właśnie z PESEL-a)."""
    age = str(form_data.get("age", "")).strip()
    pesel = str(form_data.get("pesel", "")).strip()

    if not age.isdigit() or not pesel:
        return []

    pesel_age = _age_from_pesel(pesel)
    if pesel_age is None:
        return []

    if abs(int(age) - pesel_age) > 1:
        return [{
            "severity": "warning",
            "source": "rules",
            "code": "age_pesel_mismatch",
            "field": "age",
            "message": "Age does not match the date of birth encoded in PESEL.",
            "evidence": f"age={age} pesel_age={pesel_age}",
        }]

    return []

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

# Łańcuch wymiarów "AxBxC cm" — jednostka na końcu dotyczy wszystkich liczb w łańcuchu.
DIMENSION_CHAIN_PATTERN = re.compile(
    r"(\d+(?:[,.]\d+)?(?:\s*[x×]\s*\d+(?:[,.]\d+)?)*)\s*(mm|cm|metrów|metry|metra|metr|m)\b"
)


def _iter_dimensions(text: str):
    """Zwraca (wartość, jednostka) dla każdej liczby w opisie — również z łańcuchów
    typu "40 x 30 x 20 cm" (bez tego łapana byłaby tylko ostatnia liczba przed jednostką)."""
    for chain, unit in DIMENSION_CHAIN_PATTERN.findall(str(text or "").lower()):
        for raw_value in re.split(r"\s*[x×]\s*", chain.strip()):
            raw_value = raw_value.strip()
            if raw_value:
                yield raw_value, unit

def check_dimensions(transcript: str, form_data: dict) -> list:
    """Skanuje wymiary osobno w opisie i w transkrypcji, żeby `field` w issue
    wiernie mówił, skąd pochodzi wartość. Wymiar obecny w obu miejscach jest
    raportowany raz — przypisany do `description`."""
    issues = []
    seen = set()  # (field, code, evidence)
    described_evidence = set()

    organ = _resolve_organ(form_data)
    limit_cm = ORGAN_MAX_DIMENSION_CM.get(organ, GLOBAL_MAX_DIMENSION_CM)

    def scan(text: str, field: str) -> None:
        for raw_value, raw_unit in _iter_dimensions(text):
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

            if value_cm is not None and value_cm > limit_cm:
                if organ is not None:
                    add_issue(
                        "warning",
                        "implausible_dimension_for_organ",
                        f"Dimension exceeds plausible size for organ '{organ}' (limit {limit_cm} cm).",
                    )
                else:
                    add_issue("warning", "suspicious_large_dimension", "Suspiciously large dimension detected.")

    scan(form_data.get("description", ""), "description")
    scan(transcript, "transcript")

    return issues

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
    """Return {"ran": bool, "issues": list, "reason": str} for optional LLM review."""
    api_key, url = llm_api_config()

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
            url=url,
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
            return {"ran": True, "issues": [], "reason": "http_error"}

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
            if severity not in SANITY_ALLOWED_SEVERITIES:
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
        return {"ran": True, "issues": [], "reason": "exception"}


if __name__ == "__main__":
    sample = {
        "organ": "nerka",
        "name": "Test Patient",
        "age": "82",
        "pesel": "44051401359",
        "description": "Bioptat nerki o dlugosci 1,5 cm.",
    }
    result = run_data_sanity_check("Bioptat nerki o dlugosci 1,5 cm.", sample)
    assert result["status"] in {"ok", "warning", "critical"}
    assert result["llm_review"]["ran"] is False
    assert result["repair"]["ran"] is False
    print("Data sanity check self-check passed")
