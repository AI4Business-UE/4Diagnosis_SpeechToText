from app_stt.services import data_sanity_check

import run_eval


class FakePipelineConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.use_volume_normalization = False
        self.use_bandpass_filter = False
        self.use_noise_reduction = False
        self.use_vad = False


class FakePipeline:
    run_calls = 0

    def __init__(self, config):
        assert config.enable_sanity_check is False

    def run(self, audio_path):
        FakePipeline.run_calls += 1
        return {
            "transcript": "raw transcript",
            "corrected_transcript": "guz 3 cm",
            "entities": {
                "patient": {"first_name": "Jan", "last_name": "Nowak", "age": 42, "pesel": ""},
                "components": [{"name": "tarczyca"}],
                "lesions": [],
                "fluid_samples": [],
            },
            "form_data": {
                "name": "Jan Nowak",
                "organ": "tarczyca",
                "age": "42",
                "pesel": "",
                "description": "guz 3 cm",
            },
            "sanity_result": {"status": "should_not_be_used"},
        }


def test_audio_sanity_eval_runs_pipeline_once_per_sample_and_compares_modes(monkeypatch, tmp_path):
    FakePipeline.run_calls = 0
    monkeypatch.setattr(run_eval, "load_pipeline_classes", lambda: (FakePipelineConfig, FakePipeline))

    rows = run_eval._run_sanity_audio(
        {
            "models": ["whisper-small"],
            "preprocessing": ["baseline"],
            "ner_strategies": ["chained"],
            "llm_model": "openai/gpt-4o",
            "sanity_modes": ["rules", "rules_and_llm"],
        },
        data_sanity_check,
        [{"sample_id": "s1", "audio_path": "sample.wav", "audio_file": "sample.wav"}],
        tmp_path,
    )

    assert FakePipeline.run_calls == 1
    assert [row["sanity_mode"] for row in rows] == ["rules", "rules_and_llm"]
    assert [row["llm_reason"] for row in rows] == ["mode_rules", "no_api_key"]
    assert all(row["status"] != "should_not_be_used" for row in rows)


def test_build_sanity_row_adds_score_bucket_and_severity_match():
    ok_row = run_eval._build_sanity_row(
        data_sanity_check,
        {"status": "ok", "score": 1.0, "issues": [], "metrics": {}, "llm_review": {}},
        {"sample_id": "ok", "expected_severity": "ok"},
        {},
    )
    major_row = run_eval._build_sanity_row(
        data_sanity_check,
        {
            "status": "warning",
            "score": 0.75,
            "issues": [{"severity": "warning", "source": "rules", "code": "x", "field": "description"}],
            "metrics": {},
            "llm_review": {},
        },
        {"sample_id": "major", "expected_severity": "major"},
        {},
    )
    critical_row = run_eval._build_sanity_row(
        data_sanity_check,
        {
            "status": "critical",
            "score": 0.9,
            "issues": [{"severity": "error", "source": "rules", "code": "x", "field": "description"}],
            "metrics": {},
            "llm_review": {},
        },
        {"sample_id": "critical", "expected_severity": "critical"},
        {},
    )

    assert ok_row["score_bucket"] == "ok"
    assert ok_row["severity_match"] is True
    assert major_row["score_bucket"] == "major"
    assert major_row["severity_match"] is True
    assert critical_row["score_bucket"] == "critical"
    assert critical_row["severity_match"] is True


def test_build_sanity_row_matches_expected_issue_codes():
    row = run_eval._build_sanity_row(
        data_sanity_check,
        {
            "status": "warning",
            "score": 0.75,
            "issues": [
                {"severity": "warning", "source": "rules", "code": "age_pesel_mismatch", "field": "age"},
                {"severity": "warning", "source": "rules", "code": "extra_warning", "field": "description"},
            ],
            "metrics": {},
            "llm_review": {},
        },
        {"sample_id": "codes", "expected_issue_codes": ["age_pesel_mismatch"]},
        {},
    )

    assert row["expected_issue_codes"] == "age_pesel_mismatch"
    assert row["issue_code_match"] is True
    assert row["missing_expected_issue_codes"] == ""
    assert row["unexpected_issue_codes"] == "extra_warning"


def test_build_sanity_row_reports_missing_expected_issue_codes():
    row = run_eval._build_sanity_row(
        data_sanity_check,
        {
            "status": "warning",
            "score": 0.75,
            "issues": [{"severity": "warning", "source": "rules", "code": "age_pesel_mismatch", "field": "age"}],
            "metrics": {},
            "llm_review": {},
        },
        {"sample_id": "missing", "expected_issue_codes": "age_pesel_mismatch|invalid_pesel_date"},
        {},
    )

    assert row["issue_code_match"] is False
    assert row["missing_expected_issue_codes"] == "invalid_pesel_date"
    assert row["unexpected_issue_codes"] == ""


def test_build_sanity_row_leaves_issue_code_rubric_empty_without_expected_codes():
    row = run_eval._build_sanity_row(
        data_sanity_check,
        {
            "status": "warning",
            "score": 0.85,
            "issues": [{"severity": "warning", "source": "rules", "code": "description_not_meaningful", "field": "description"}],
            "metrics": {},
            "llm_review": {},
        },
        {"sample_id": "no-rubric"},
        {},
    )

    assert row["expected_issue_codes"] == ""
    assert row["issue_code_match"] == ""
    assert row["missing_expected_issue_codes"] == ""
    assert row["unexpected_issue_codes"] == ""
