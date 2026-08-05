import re
import json
import os
import importlib.util
from datetime import datetime
from pathlib import Path

import requests

try:
    from app_stt.data.sanity_terms import (
        LESION_WORDS,
        REQUIRED_FORM_FIELDS,
        SANITY_ALLOWED_SEVERITIES,
    )
except ModuleNotFoundError:
    terms_path = Path(__file__).resolve().parents[1] / "data" / "sanity_terms.py"
    terms_spec = importlib.util.spec_from_file_location("sanity_terms", terms_path)
    if terms_spec is None or terms_spec.loader is None:
        LESION_WORDS = []
        REQUIRED_FORM_FIELDS = ["organ", "name", "age", "pesel", "description"]
        SANITY_ALLOWED_SEVERITIES = {"error", "warning", "info"}
    else:
        terms_module = importlib.util.module_from_spec(terms_spec)
        terms_spec.loader.exec_module(terms_module)
        LESION_WORDS = getattr(terms_module, "LESION_WORDS", [])
        REQUIRED_FORM_FIELDS = getattr(
            terms_module,
            "REQUIRED_FORM_FIELDS",
            ["organ", "name", "age", "pesel", "description"],
        )
        SANITY_ALLOWED_SEVERITIES = getattr(
            terms_module,
            "SANITY_ALLOWED_SEVERITIES",
            {"error", "warning", "info"},
        )

try:
    from logging_config import logger
except ModuleNotFoundError:  # pozwala uruchomić self-check standalone (bez ścieżki Django)
    import logging
    logger = logging.getLogger("data_sanity_check")


def _load_organ_plausibility() -> tuple[dict, float, list]:
    """Ładuje zakresy per narząd z data/organ_plausibility.py po ścieżce (importlib),
    żeby działało i w Django, i przy standalone self-check."""
    path = Path(__file__).resolve().parents[1] / "data" / "organ_plausibility.py"
    spec = importlib.util.spec_from_file_location("organ_plausibility", path)
    if spec is None or spec.loader is None:
        return {}, 50.0, []
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return (
        getattr(module, "ORGAN_MAX_DIMENSION_CM", {}),
        getattr(module, "GLOBAL_MAX_DIMENSION_CM", 50.0),
        getattr(module, "ORGAN_STEMS", []),
    )


ORGAN_MAX_DIMENSION_CM, GLOBAL_MAX_DIMENSION_CM, ORGAN_STEMS = _load_organ_plausibility()

SANITY_MODES = {"rules", "rules_and_llm"}


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
    "missing_required_field": 0.08,
    "invalid_pesel_length": 0.25,
    "invalid_pesel_format": 0.25,
    "invalid_pesel_checksum": 0.3,
    "invalid_pesel_date": 0.3,
    "age_not_a_number": 0.2,
    "age_too_high": 0.2,
    "negative_age": 0.3,
    "age_pesel_mismatch": 0.2,
    "description_not_meaningful": 0.15,
    "non_positive_dimension": 0.5,
    "suspicious_unit_meter": 0.15,
    "suspicious_large_dimension": 0.15,
    "implausible_dimension_for_organ": 0.2,
    "lesion_without_dimension": 0.1,
    "possible_lesion_omitted": 0.15,
}


def run_data_sanity_check(transcript: str, form_data: dict, mode: str = "rules") -> dict:
    """Run sanity QA in a selected mode.

    Default `rules` is deterministic and never uses the network. `rules_and_llm`
    adds an opt-in LLM review for eval experiments.
    """
    if mode not in SANITY_MODES:
        raise ValueError(f"Unknown sanity mode '{mode}'. Supported: {', '.join(sorted(SANITY_MODES))}.")

    issues = []

    issues += check_required_fields(form_data)
    issues += check_description_quality(form_data)
    issues += check_pesel(form_data)
    issues += check_age(form_data)
    issues += check_age_pesel_consistency(form_data)
    issues += check_dimensions(transcript, form_data)
    issues += check_description_consistency(transcript, form_data)

    llm = {"ran": False, "issues": [], "reason": "mode_rules"}
    if mode == "rules_and_llm":
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
    zakresy stuleci (miesiąc +0/+20/+40/+60/+80 → 1900/2000/2100/2200/1800). Osobno od
    _age_from_pesel, żeby nie zmieniać produkcyjnej logiki wieku."""
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
    """Wiek z daty urodzenia zakodowanej w PESEL-u. Lustro logiki z
    audio_consumers.calculate_age_from_pesel. Zwraca None gdy PESEL/data są niepoprawne."""
    pesel = str(pesel or "").strip()
    if len(pesel) != 11 or not pesel.isdigit():
        return None

    try:
        year = int(pesel[0:2])
        month = int(pesel[2:4])
        day = int(pesel[4:6])

        if 1 <= month <= 12:
            century = 1900
        elif 21 <= month <= 32:
            century = 2000
            month -= 20
        else:
            return None

        birth_date = datetime(century + year, month, day)
        today = datetime.today()
        return today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )
    except (ValueError, IndexError):
        return None

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
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_KEY")
    url = "https://openrouter.ai/api/v1/chat/completions"
    if not api_key and os.getenv("OPENAI_API_KEY"):
        api_key = os.getenv("OPENAI_API_KEY")
        url = "https://api.openai.com/v1/chat/completions"

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
        return {"ran": False, "issues": [], "reason": "exception"}


def _self_check() -> None:
    saved_keys = {
        name: os.environ.pop(name, None)
        for name in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "OPENAI_KEY", "SANITY_LLM_MODEL")
    }
    try:
        assert LESION_WORDS
        assert {"organ", "name", "age", "pesel", "description"}.issubset(REQUIRED_FORM_FIELDS)
        assert {"error", "warning", "info"}.issubset(SANITY_ALLOWED_SEVERITIES)

        five_warnings = [{"severity": "warning", "code": "missing_required_field"} for _ in range(5)]
        score_five = calculate_score(five_warnings)
        assert 0.0 < score_five < 1.0
        assert score_five > calculate_score([{"severity": "error", "code": "non_positive_dimension"}])

        assert derive_status([]) == "ok"
        assert derive_status([{"severity": "warning", "code": "x"}]) == "warning"
        assert derive_status([{"severity": "error", "code": "x"}]) == "critical"

        only_transcript = check_dimensions("guz 60 cm", {"description": ""})
        assert any(issue["field"] == "transcript" for issue in only_transcript)
        only_description = check_dimensions("", {"description": "guz 60 cm"})
        assert any(issue["field"] == "description" for issue in only_description)
        both = check_dimensions("guz 60 cm", {"description": "guz 60 cm"})
        large = [issue for issue in both if issue["code"] == "suspicious_large_dimension"]
        assert len(large) == 1 and large[0]["field"] == "description"

        assert LESION_PATTERN.search("guz") is not None
        assert LESION_PATTERN.search("guzik") is None
        assert check_dimensions("BAL 20 ml", {"description": "materiał 20 ml"}) == []
        assert check_dimensions("", {"description": "guz 60 cm"}) != []

        kidney_big = check_dimensions("", {"organ": "nerka", "description": "guz 40 cm"})
        assert any(issue["code"] == "implausible_dimension_for_organ" for issue in kidney_big)
        kidney_chain = check_dimensions("", {"organ": "nerka", "description": "guz 40 x 30 x 20 cm"})
        assert any(
            issue["code"] == "implausible_dimension_for_organ" and issue["evidence"] == "40 cm"
            for issue in kidney_chain
        )
        assert check_dimensions("", {"organ": "nerka", "description": "guz 8 cm"}) == []
        assert check_dimensions("", {"organ": "macica", "description": "trzon 9 cm"}) == []
        assert _resolve_organ({"organ": "nerki prawej"}) == "nerka"
        assert _resolve_organ({"organ": "szyjka macicy"}) == "szyjka macicy"
        unknown_organ = check_dimensions("", {"organ": "", "description": "tkanka 300 cm"})
        assert any(issue["code"] == "suspicious_large_dimension" for issue in unknown_organ)

        pesel_age = _age_from_pesel("44051401359")
        assert pesel_age is not None
        assert check_age_pesel_consistency({"age": str(pesel_age), "pesel": "44051401359"}) == []
        mismatch = check_age_pesel_consistency({"age": str(pesel_age + 30), "pesel": "44051401359"})
        assert any(issue["code"] == "age_pesel_mismatch" for issue in mismatch)
        assert check_age_pesel_consistency({"age": "40", "pesel": ""}) == []

        assert any(issue["code"] == "negative_age" for issue in check_age({"age": "-5"}))
        assert any(issue["code"] == "age_not_a_number" for issue in check_age({"age": "abc"}))

        for bad_date_pesel in ("99133212341", "00223012345", "22423112340"):
            assert any(issue["code"] == "invalid_pesel_date" for issue in check_pesel({"pesel": bad_date_pesel}))
        assert not any(issue["code"] == "invalid_pesel_date" for issue in check_pesel({"pesel": "44051401359"}))
        assert _pesel_birth_date("05210112345") is not None
        assert any(issue["code"] == "invalid_pesel_date" for issue in check_pesel({"pesel": "99323100009"}))

        assert check_description_quality({"description": "."})[0]["code"] == "description_not_meaningful"
        assert check_description_quality({"description": "3 cm"})[0]["code"] == "description_not_meaningful"
        assert check_description_quality({"description": "Fragment nerki 8 cm."}) == []
        assert check_description_quality({"description": "   "}) == []

        result = run_data_sanity_check("guz 3 cm", {
            "organ": "", "name": "", "age": "", "pesel": "", "description": "",
        })
        assert result["status"] in {"ok", "warning", "critical"}
        assert result["llm_review"] == {"ran": False, "reason": "mode_rules", "issue_count": 0}

        llm_result = run_data_sanity_check("guz 3 cm", {
            "organ": "", "name": "", "age": "", "pesel": "", "description": "",
        }, mode="rules_and_llm")
        assert llm_result["status"] in {"ok", "warning", "critical"}
        assert llm_result["llm_review"]["ran"] is False
        assert llm_result["llm_review"]["reason"] == "no_api_key"

        try:
            run_data_sanity_check("", {}, mode="bad_mode")
            assert False
        except ValueError:
            pass
    finally:
        for name, value in saved_keys.items():
            if value is not None:
                os.environ[name] = value


if __name__ == "__main__":
    _self_check()
    print("Data sanity check self-check passed")
