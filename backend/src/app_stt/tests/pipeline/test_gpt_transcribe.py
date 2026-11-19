import tempfile
from types import SimpleNamespace

from django.test import TestCase

from app_stt.models import Keyword
from app_stt.pipeline.stages.stt.gpt_transcribe import GPTTranscribe


class FakeGateway:
    """Podwójna brama LLM — rejestruje wywołania transcribe bez wire-shape'u."""

    def __init__(self):
        self.calls = []

    def transcribe(self, audio_path, model_ref, *, keywords=None,
                   languages=None, prompt=None, temperature=None):
        self.calls.append({
            "audio_path": audio_path,
            "model_ref": model_ref,
            "keywords": keywords,
            "languages": languages,
            "prompt": prompt,
            "temperature": temperature,
        })
        return SimpleNamespace(text="Wynik transkrypcji")


class GPTTranscribeTests(TestCase):
    def transcribe(self, gateway, model_ref="openai/gpt-transcribe"):
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            audio_file.write(b"audio")
            audio_file.flush()
            result = GPTTranscribe(model_ref=model_ref, gateway=gateway).transcribe(audio_file.name)
        return result, audio_file.name

    def test_sends_catalog_keywords_polish_language_and_pathology_prompt_to_gateway(self):
        Keyword.objects.create(text="Żółciak")
        Keyword.objects.create(text="Torbiel")
        gateway = FakeGateway()

        result, audio_path = self.transcribe(gateway)

        self.assertEqual(result, "Wynik transkrypcji")
        self.assertEqual(len(gateway.calls), 1)
        call = gateway.calls[0]
        self.assertEqual(call["audio_path"], audio_path)
        self.assertEqual(call["keywords"], ["Żółciak", "Torbiel"])
        self.assertEqual(call["languages"], ["pl"])
        self.assertIn("badania patomorfologicznego", call["prompt"])

    def test_transcribes_with_the_injected_model_reference(self):
        gateway = FakeGateway()

        self.transcribe(gateway, model_ref="openai/whisper-1")

        self.assertEqual(gateway.calls[0]["model_ref"], "openai/whisper-1")

    def test_passes_empty_keyword_list_when_catalog_is_empty(self):
        gateway = FakeGateway()

        self.transcribe(gateway)

        self.assertEqual(gateway.calls[0]["keywords"], [])
