import json

from app_stt.services.sanity_logging import append_sanity_record


def test_append_sanity_record_writes_sanitized_jsonl(tmp_path):
    log_path = tmp_path / "runtime_sanity.jsonl"
    sanity_result = {
        "status": "warning",
        "score": 0.82,
        "issues": [
            {
                "severity": "warning",
                "source": "rules",
                "code": "age_pesel_mismatch",
                "field": "age",
                "message": "Age does not match the date of birth encoded in PESEL.",
                "evidence": "age=42 pesel_age=82",
            }
        ],
        "metrics": {
            "transcript_length": 420,
            "description_length": 390,
        },
    }

    record = append_sanity_record(sanity_result, log_path)
    stored = json.loads(log_path.read_text(encoding="utf-8").strip())

    assert stored == record
    assert stored["status"] == "warning"
    assert stored["score"] == 0.82
    assert stored["issue_count"] == 1
    assert stored["issue_codes"] == ["age_pesel_mismatch"]
    assert stored["issue_fields"] == ["age"]
    assert stored["transcript_length"] == 420
    assert stored["description_length"] == 390

    for forbidden_key in ("form_data", "formData", "pesel", "name", "evidence", "corrected_text"):
        assert forbidden_key not in stored
        assert all(forbidden_key not in issue for issue in stored["issues"])
