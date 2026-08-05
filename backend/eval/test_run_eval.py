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
