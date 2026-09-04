"""Testy guardraila data sanity.

Weryfikują reguły, scoring, dekodowanie PESEL, wymiary oraz tryby
rules / rules_and_llm / review_and_repair. Sanity to guardrail w produkcyjnym
pipeline, więc chcemy, żeby pilnował tego `pytest`/CI, a nie ręczne uruchomienie.
"""

import os
import sys
from pathlib import Path

# App i eval importują moduły jako `app_stt.*` (z `backend/src` na ścieżce). Pytest widzi
# pakiet jako `src.app_stt`, więc dokładamy `backend/src`, żeby importy w module się zgadzały.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app_stt.services.data_sanity_check import (
    LESION_PATTERN,
    LESION_WORDS,
    REQUIRED_FORM_FIELDS,
    SANITY_ALLOWED_SEVERITIES,
    _age_from_pesel,
    _pesel_birth_date,
    _resolve_organ,
    calculate_score,
    check_age,
    check_age_pesel_consistency,
    check_description_quality,
    check_dimensions,
    check_pesel,
    derive_status,
    run_data_sanity_check,
    validated_repaired_form_data,
)


def test_terms_and_severities_loaded():
    assert LESION_WORDS
    assert {"organ", "name", "age", "pesel", "description"}.issubset(REQUIRED_FORM_FIELDS)
    assert {"error", "warning", "info"}.issubset(SANITY_ALLOWED_SEVERITIES)


def test_scoring_and_status():
    five_warnings = [{"severity": "warning", "code": "missing_required_field"} for _ in range(5)]
    score_five = calculate_score(five_warnings)
    assert 0.0 < score_five < 1.0
    assert score_five > calculate_score([{"severity": "error", "code": "non_positive_dimension"}])

    assert derive_status([]) == "ok"
    assert derive_status([{"severity": "warning", "code": "x"}]) == "warning"
    assert derive_status([{"severity": "error", "code": "x"}]) == "critical"


def test_dimensions_source_and_dedup():
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


def test_organ_plausibility():
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


def test_pesel_and_age():
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


def test_description_quality():
    assert check_description_quality({"description": "."})[0]["code"] == "description_not_meaningful"
    assert check_description_quality({"description": "3 cm"})[0]["code"] == "description_not_meaningful"
    assert check_description_quality({"description": "Fragment nerki 8 cm."}) == []
    assert check_description_quality({"description": "   "}) == []


def test_modes_without_api_key():
    """Bez kluczy API tryby LLM nie wychodzą do sieci — sprawdzamy metadane."""
    saved_keys = {
        name: os.environ.pop(name, None)
        for name in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "OPENAI_KEY", "SANITY_LLM_MODEL")
    }
    try:
        empty_form = {"organ": "", "name": "", "age": "", "pesel": "", "description": ""}

        result = run_data_sanity_check("guz 3 cm", empty_form)
        assert result["status"] in {"ok", "warning", "critical"}
        assert result["llm_review"] == {"ran": False, "reason": "mode_rules", "issue_count": 0}
        assert result["repair"]["ran"] is False
        assert result["repair"]["reason"] == "mode_rules"

        llm_result = run_data_sanity_check("guz 3 cm", empty_form, mode="rules_and_llm")
        assert llm_result["status"] in {"ok", "warning", "critical"}
        assert llm_result["llm_review"]["ran"] is False
        assert llm_result["llm_review"]["reason"] == "no_api_key"
        assert llm_result["repair"]["ran"] is False
        assert llm_result["repair"]["reason"] == "mode_rules_and_llm"

        repair_result = run_data_sanity_check(
            "guz 3 cm", empty_form, mode="review_and_repair", repair_scope="description"
        )
        assert repair_result["repair"]["ran"] is False
        assert repair_result["repair"]["reason"] == "no_api_key"
        assert repair_result["repair"]["scope"] == "description"
        assert repair_result["original_issue_count"] >= 1
    finally:
        for name, value in saved_keys.items():
            if value is not None:
                os.environ[name] = value


def test_scoped_repair_validation():
    scoped_form, scoped_changes = validated_repaired_form_data(
        {"name": "", "age": "", "pesel": "", "organ": "", "description": ""},
        {
            "repaired_form_data": {
                "name": "Jan Nowak",
                "organ": "tarczyca",
                "description": "Fragment tarczycy.",
                "unexpected": "x",
            },
            "changes": [],
        },
        "description",
        "Fragment tarczycy.",
    )
    assert scoped_form["name"] == ""
    assert scoped_form["organ"] == "tarczyca"
    assert scoped_form["description"] == "Fragment tarczycy."
    assert {change["field"] for change in scoped_changes} == {"description", "organ"}


def test_invalid_modes_and_scopes():
    import pytest

    with pytest.raises(ValueError):
        run_data_sanity_check("", {}, mode="bad_mode")
    assert run_data_sanity_check("", {}, mode="rules", repair_scope="bad_scope")["repair"]["ran"] is False
    assert run_data_sanity_check("", {}, mode="rules_and_llm", repair_scope="bad_scope")["repair"]["ran"] is False
    with pytest.raises(ValueError):
        run_data_sanity_check("", {}, mode="review_and_repair", repair_scope="bad_scope")
