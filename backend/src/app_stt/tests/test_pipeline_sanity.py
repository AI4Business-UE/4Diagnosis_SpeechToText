from app_stt.pipeline.config import PipelineConfig
from app_stt.pipeline.pipeline import Pipeline
from app_stt.pipeline.stages.ner.base import ExtractionResult
from app_stt.pipeline.stages.ner.entities import Component, Patient


class FakePreprocessor:
    def process(self, audio_path):
        return {"output_path": audio_path}


class FakeSTT:
    def transcribe(self, audio_path):
        return {"text": "Pacjent Jan Nowak, lat 42. Tarczyca, guz 3 cm."}


class FakeNER:
    def extract(self, transcript):
        return ExtractionResult(
            patient=Patient(first_name="Jan", last_name="Nowak", age=42),
            components=[Component(name="tarczyca")],
        )


class FakeRAG:
    def retrieve_fusion(self, **kwargs):
        return []


class FakeAnswerer:
    def correct_transcription(self, transcript, templates, entities):
        return "Pacjent Jan Nowak, lat 42. Tarczyca, guz 3 cm."


def _fake_pipeline(enable_sanity_check):
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.config = PipelineConfig(
        enable_sanity_check=enable_sanity_check,
        sanity_mode="rules",
    )
    pipeline.preprocessor = FakePreprocessor()
    pipeline.stt = FakeSTT()
    pipeline.ner = FakeNER()
    pipeline.rag = FakeRAG()
    pipeline.answerer = FakeAnswerer()
    return pipeline


def test_pipeline_run_returns_sanity_result_when_enabled():
    result = _fake_pipeline(enable_sanity_check=True).run("sample.wav")

    assert result["form_data"]["name"] == "Jan Nowak"
    assert result["form_data"]["organ"] == "tarczyca"
    assert result["sanity_result"] is not None
    assert result["sanity_result"]["llm_review"]["ran"] is False


def test_pipeline_run_skips_sanity_result_when_disabled():
    result = _fake_pipeline(enable_sanity_check=False).run("sample.wav")

    assert result["form_data"]["name"] == "Jan Nowak"
    assert result["sanity_result"] is None
