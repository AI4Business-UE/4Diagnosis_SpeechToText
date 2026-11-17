import os
from unittest.mock import patch

from django.test import SimpleTestCase

from app_stt.pipeline.config import PipelineConfig
from app_stt.pipeline.pipeline import Pipeline
from app_stt.pipeline.stages.ner.ttt_fallback import TTTFallbackStrategy
from app_stt.pipeline.utils.llm.gateway import reset_gateway


class PipelineTests(SimpleTestCase):
    def tearDown(self):
        reset_gateway()

    def test_hosted_stt_fails_during_pipeline_construction_without_host_key(self):
        with (
            patch.dict(os.environ, {"LLM_HOST": "openai", "OPENAI_API_KEY": ""}),
            patch("app_stt.pipeline.pipeline.AudioPreprocessor"),
        ):
            with self.assertRaisesRegex(ValueError, "Brak klucza API Hosta 'openai'"):
                Pipeline(PipelineConfig(stt_model="gpt-transcribe"))

    def test_local_stt_keeps_ttt_fallback_when_host_is_unconfigured(self):
        with (
            patch.dict(os.environ, {"LLM_HOST": "openai", "OPENAI_API_KEY": ""}),
            patch("app_stt.pipeline.pipeline.AudioPreprocessor"),
            patch("app_stt.pipeline.pipeline.WhisperLocal"),
            patch("app_stt.pipeline.pipeline.QdrantRetriever"),
        ):
            pipeline = Pipeline(PipelineConfig(stt_model="whisper_local"))

        self.assertIsInstance(pipeline.ner, TTTFallbackStrategy)
