import tempfile
from types import SimpleNamespace

from django.test import SimpleTestCase

from app_stt.pipeline.stages.stt.whisper_hosted import WhisperHosted


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


class WhisperHostedTests(SimpleTestCase):
    def test_declares_polish_language_and_zero_temperature_through_gateway(self):
        gateway = FakeGateway()

        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            audio_file.write(b"audio")
            audio_file.flush()
            result = WhisperHosted(
                model_ref="openai/whisper-1", gateway=gateway
            ).transcribe(audio_file.name)

        self.assertEqual(result, "Wynik transkrypcji")
        self.assertEqual(len(gateway.calls), 1)
        call = gateway.calls[0]
        self.assertEqual(call["audio_path"], audio_file.name)
        self.assertEqual(call["model_ref"], "openai/whisper-1")
        self.assertEqual(call["languages"], ["pl"])
        self.assertEqual(call["temperature"], 0)
        self.assertIsNone(call["keywords"])
        self.assertIsNone(call["prompt"])
