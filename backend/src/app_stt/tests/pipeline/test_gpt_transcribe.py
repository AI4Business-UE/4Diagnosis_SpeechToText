import base64
import json
import tempfile
from unittest.mock import patch

import httpx
from django.test import TestCase
from openai import OpenAI

from app_stt.models import Keyword
from app_stt.pipeline.stages.stt.gpt_transcribe import GPTTranscribe


class GPTTranscribeTests(TestCase):
    def transcribe_with_mocked_openrouter(self, audio_path, requests):
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={"text": "Wynik transkrypcji"})

        client = OpenAI(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        )
        with patch(
            "app_stt.pipeline.stages.stt.gpt_transcribe.get_llm_client",
            return_value=client,
        ):
            result = GPTTranscribe().transcribe(audio_path)
        client.close()
        return result

    def test_sends_database_keywords_as_openrouter_json_and_returns_transcript(self):
        Keyword.objects.create(text="Żółciak")
        Keyword.objects.create(text="Torbiel")
        requests = []
        audio = b"wav audio bytes"
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            audio_file.write(audio)
            audio_file.flush()

            result = self.transcribe_with_mocked_openrouter(audio_file.name, requests)

        self.assertEqual(result, "Wynik transkrypcji")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.path, "/api/v1/audio/transcriptions")
        body = json.loads(requests[0].content)
        self.assertEqual(body["model"], "openai/gpt-transcribe")
        self.assertEqual(
            body["input_audio"],
            {"data": base64.b64encode(audio).decode("ascii"), "format": "wav"},
        )
        self.assertEqual(
            body["provider"]["options"]["openai"]["keywords"],
            ["Żółciak", "Torbiel"],
        )
        self.assertEqual(body["provider"]["options"]["openai"]["languages"], ["pl"])
        self.assertIn("badania patomorfologicznego", body["provider"]["options"]["openai"]["prompt"])

    def test_sends_empty_keyword_list_when_catalog_is_empty(self):
        requests = []
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            audio_file.write(b"audio")
            audio_file.flush()

            self.transcribe_with_mocked_openrouter(audio_file.name, requests)

        body = json.loads(requests[0].content)
        self.assertEqual(body["provider"]["options"]["openai"]["keywords"], [])
