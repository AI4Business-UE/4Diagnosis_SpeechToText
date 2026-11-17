import base64
import json
import os
import tempfile
from contextlib import contextmanager

import httpx
from django.test import SimpleTestCase
from openai import OpenAI

from app_stt.pipeline.utils.llm.gateway import (
    LLMGateway,
    active_host,
    get_gateway,
    is_configured,
    reset_gateway,
)


@contextmanager
def _env(**values):
    """Set os.environ to exactly `values` for the block (None removes)."""
    saved = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class _ModelRefChecks:
    def test_openrouter_passes_model_reference_through_untouched(self):
        gw = LLMGateway(client=None, host="openrouter")
        self.assertEqual(gw.resolve_model_ref("openai/gpt-6-luna"), "openai/gpt-6-luna")

    def test_openai_strips_openai_vendor_prefix(self):
        gw = LLMGateway(client=None, host="openai")
        self.assertEqual(gw.resolve_model_ref("openai/gpt-transcribe"), "gpt-transcribe")

    def test_openai_rejects_foreign_vendor_with_polish_error(self):
        gw = LLMGateway(client=None, host="openai")
        with self.assertRaises(ValueError) as ctx:
            gw.resolve_model_ref("google/gemini-2.5-flash")
        self.assertIn("Host OpenAI nie obsługuje", str(ctx.exception))
        self.assertIn("google/gemini-2.5-flash", str(ctx.exception))

    def test_openai_rejects_reference_without_vendor_prefix(self):
        gw = LLMGateway(client=None, host="openai")
        with self.assertRaises(ValueError) as ctx:
            gw.resolve_model_ref("gpt-transcribe")
        self.assertIn("Host OpenAI nie obsługuje", str(ctx.exception))


PATHOLOGY_PROMPT = (
    "Nagranie badania patomorfologicznego w języku polskim. Lekarz mówiący może okazjonalnie się poprawiać, "
    "np. poprawnie 'torbielowaty, nie, litowy', zamiast 'torbielowaty, nielitowy.'"
)


def _mock_client(respond):
    return OpenAI(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )


class _OpenRouterTranscribeChecks:
    """Kontrakt wire Hosta OpenRouter: JSON + base64 input_audio + envelope
    provider.options (zachowany behawioralnie 1:1 ze stanem przed refaktorem)."""

    def _transcribe_openrouter(self, keywords, requests):
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={"text": "Wynik transkrypcji"})

        client = _mock_client(respond)
        gw = LLMGateway(client=client, host="openrouter")
        audio = b"wav audio bytes"
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            audio_file.write(audio)
            audio_file.flush()
            result = gw.transcribe(
                audio_file.name,
                "openai/gpt-transcribe",
                keywords=keywords,
                languages=["pl"],
                prompt=PATHOLOGY_PROMPT,
            )
        client.close()
        return result, audio

    def test_sends_reference_and_base64_audio_as_json_body(self):
        requests = []
        result, audio = self._transcribe_openrouter(["Żółciak", "Torbiel"], requests)

        self.assertEqual(result.text, "Wynik transkrypcji")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.path, "/api/v1/audio/transcriptions")
        body = json.loads(requests[0].content)
        self.assertEqual(body["model"], "openai/gpt-transcribe")
        self.assertEqual(
            body["input_audio"],
            {"data": base64.b64encode(audio).decode("ascii"), "format": "wav"},
        )
        self.assertNotIn("temperature", body)

    def test_wraps_domain_policy_in_provider_options_for_the_reference_vendor(self):
        requests = []
        self._transcribe_openrouter(["Żółciak", "Torbiel"], requests)

        body = json.loads(requests[0].content)
        options = body["provider"]["options"]["openai"]
        self.assertEqual(options["keywords"], ["Żółciak", "Torbiel"])
        self.assertEqual(options["languages"], ["pl"])
        self.assertIn("badania patomorfologicznego", options["prompt"])

    def test_sends_empty_keyword_list_when_catalog_is_empty(self):
        requests = []
        self._transcribe_openrouter([], requests)

        body = json.loads(requests[0].content)
        self.assertEqual(body["provider"]["options"]["openai"]["keywords"], [])

    def test_shaped_for_hosted_whisper_partial_envelope_and_temperature(self):
        """Kształt, który realnie wysyła etap whisper_hosted: tylko język i
        temperatura — envelope `provider.options` zawiera wyłącznie `languages`."""
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={"text": "Wynik"})

        client = _mock_client(respond)
        gw = LLMGateway(client=client, host="openrouter")
        requests = []
        with tempfile.NamedTemporaryFile(suffix=".mp3") as audio_file:
            audio_file.write(b"audio")
            audio_file.flush()
            gw.transcribe(audio_file.name, "openai/whisper-1",
                          languages=["pl"], temperature=0)
        client.close()

        body = json.loads(requests[0].content)
        self.assertEqual(body["model"], "openai/whisper-1")
        self.assertEqual(body["temperature"], 0)
        self.assertEqual(body["input_audio"]["format"], "mp3")
        self.assertEqual(body["provider"]["options"]["openai"], {"languages": ["pl"]})


def _multipart_fields(request) -> dict[str, object]:
    """Parses the multipart form: scalar fields map to their value, repeated
    `name[]` array parts (how the SDK sends list values) aggregate to a list."""
    content_type = request.headers["content-type"]
    boundary = content_type.split("boundary=")[1].encode()
    fields: dict[str, list[str]] = {}
    arrays: set[str] = set()
    for part in request.content.split(b"--" + boundary):
        if b'name="' not in part:
            continue
        header, _, body = part.partition(b"\r\n\r\n")
        name = header.split(b'name="', 1)[1].split(b'"', 1)[0].decode()
        is_array = name.endswith("[]")
        key = name[:-2] if is_array else name
        if is_array:
            arrays.add(key)
        value = body.rstrip(b"\r\n").decode("utf-8", errors="replace")
        fields.setdefault(key, []).append(value)
    return {
        key: values if key in arrays else values[0]
        for key, values in fields.items()
    }


class _OpenAITranscribeChecks:
    """Kontrakt wire Hosta OpenAI: multipart z natywnym id modelu po zdjęciu
    prefiksu `openai/`, płaskie pola keywords/languages/prompt, bez pola
    `provider`."""

    def _transcribe_openai(self, requests, **call_kwargs):
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={"text": "Wynik transkrypcji"})

        client = OpenAI(
            api_key="test-key",
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        )
        gw = LLMGateway(client=client, host="openai")
        audio = b"wav audio bytes"
        kwargs = {
            "keywords": ["Żółciak", "Torbiel"],
            "languages": ["pl"],
            "prompt": PATHOLOGY_PROMPT,
        }
        kwargs.update(call_kwargs)
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            audio_file.write(audio)
            audio_file.flush()
            result = gw.transcribe(audio_file.name, "openai/gpt-transcribe", **kwargs)
        client.close()
        return result, audio

    def test_sends_multipart_with_prefix_stripped_native_model_id(self):
        requests = []
        result, _audio = self._transcribe_openai(requests)

        self.assertEqual(result.text, "Wynik transkrypcji")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.path, "/v1/audio/transcriptions")
        self.assertIn("multipart/form-data", requests[0].headers["content-type"])
        fields = _multipart_fields(requests[0])
        self.assertEqual(fields["model"], "gpt-transcribe")
        self.assertIn("file", fields)

    def test_sends_domain_policy_as_flat_fields_without_provider_envelope(self):
        requests = []
        self._transcribe_openai(requests)

        fields = _multipart_fields(requests[0])
        self.assertEqual(fields["keywords"], ["Żółciak", "Torbiel"])
        self.assertEqual(fields["languages"], ["pl"])
        self.assertIn("badania patomorfologicznego", fields["prompt"])
        self.assertNotIn("provider", fields)
        self.assertNotIn("input_audio", fields)

    def test_sends_temperature_as_native_field_when_given(self):
        requests = []
        self._transcribe_openai(requests, temperature=0, keywords=None, prompt=None)

        fields = _multipart_fields(requests[0])
        self.assertEqual(fields["temperature"], "0")
        self.assertNotIn("keywords", fields)
        self.assertNotIn("prompt", fields)


def _chat_completion_response():
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-6-luna",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": '{"patient": {}}'},
                    "finish_reason": "stop",
                }
            ],
        },
    )


class _ChatChecks:
    MESSAGES = [
        {"role": "system", "content": "Prompt"},
        {"role": "user", "content": "Transkrypt"},
    ]

    def chat(self, host, base_url, requests, model_ref="openai/gpt-6-luna"):
        def respond(request):
            requests.append(request)
            return _chat_completion_response()

        client = OpenAI(
            api_key="test-key",
            **({"base_url": base_url} if base_url else {}),
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        )
        gw = LLMGateway(client=client, host=host)
        response = gw.chat(
            model_ref,
            self.MESSAGES,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        client.close()
        return response

    def test_openrouter_chat_serves_reference_verbatim(self):
        requests = []
        response = self.chat("openrouter", "https://openrouter.ai/api/v1", requests)

        self.assertEqual(response.choices[0].message.content, '{"patient": {}}')
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.path, "/api/v1/chat/completions")
        body = json.loads(requests[0].content)
        self.assertEqual(body["model"], "openai/gpt-6-luna")
        self.assertEqual(body["messages"], self.MESSAGES)
        self.assertEqual(body["temperature"], 0.0)
        self.assertEqual(body["response_format"], {"type": "json_object"})

    def test_openai_chat_strips_vendor_prefix_from_reference(self):
        requests = []
        self.chat("openai", None, requests)

        body = json.loads(requests[0].content)
        self.assertEqual(body["model"], "gpt-6-luna")
        self.assertEqual(requests[0].url.path, "/v1/chat/completions")

    def test_openai_chat_fails_fast_on_foreign_vendor_without_http_call(self):
        requests = []
        with self.assertRaises(ValueError):
            self.chat("openai", None, requests, model_ref="google/gemini-2.5-flash")
        self.assertEqual(requests, [])


class _HostResolutionChecks:
    def test_active_host_defaults_to_openrouter_when_llm_host_unset(self):
        with _env(LLM_HOST=None):
            self.assertEqual(active_host(), "openrouter")

    def test_active_host_treats_empty_llm_host_as_unset(self):
        with _env(LLM_HOST=""):
            self.assertEqual(active_host(), "openrouter")

    def test_active_host_reads_explicit_openai_value(self):
        with _env(LLM_HOST="openai"):
            self.assertEqual(active_host(), "openai")

    def test_active_host_rejects_unknown_value_with_polish_error(self):
        with _env(LLM_HOST="openai-direct"):
            with self.assertRaises(ValueError) as ctx:
                active_host()
        self.assertIn("Nieznana wartość LLM_HOST", str(ctx.exception))
        self.assertIn("openai-direct", str(ctx.exception))


class _KeyValidationChecks:
    def test_get_gateway_raises_polish_error_when_openrouter_key_missing(self):
        with _env(LLM_HOST=None, OPENROUTER_API_KEY=None):
            with self.assertRaises(ValueError) as ctx:
                get_gateway()
        self.assertIn("OPENROUTER_API_KEY", str(ctx.exception))

    def test_get_gateway_requires_key_matching_the_selected_host_only(self):
        # The OpenRouter key present does not satisfy the OpenAI host.
        with _env(LLM_HOST="openai", OPENROUTER_API_KEY="or-key", OPENAI_API_KEY=None):
            with self.assertRaises(ValueError) as ctx:
                get_gateway()
        self.assertIn("OPENAI_API_KEY", str(ctx.exception))

    def test_get_gateway_builds_openrouter_client_on_openrouter_base_url(self):
        with _env(LLM_HOST=None, OPENROUTER_API_KEY="or-key"):
            gw = get_gateway()
        self.assertEqual(gw.host, "openrouter")
        self.assertTrue(str(gw.client.base_url).startswith("https://openrouter.ai"))

    def test_get_gateway_builds_openai_client_on_sdk_default_base_url(self):
        with _env(LLM_HOST="openai", OPENAI_API_KEY="oa-key"):
            gw = get_gateway()
        self.assertEqual(gw.host, "openai")
        self.assertTrue(str(gw.client.base_url).startswith("https://api.openai.com"))

    def test_is_configured_true_when_active_host_key_present(self):
        with _env(LLM_HOST=None, OPENROUTER_API_KEY="or-key"):
            self.assertTrue(is_configured())

    def test_is_configured_false_when_active_host_key_missing(self):
        with _env(LLM_HOST="openai", OPENAI_API_KEY=None):
            self.assertFalse(is_configured())

    def test_is_configured_rejects_unknown_llm_host_with_polish_error(self):
        with _env(LLM_HOST="opernrouter"):
            with self.assertRaises(ValueError) as ctx:
                is_configured()
        self.assertIn("Nieznana wartość LLM_HOST", str(ctx.exception))


class LLMGatewayTests(
    _ModelRefChecks,
    _OpenRouterTranscribeChecks,
    _OpenAITranscribeChecks,
    _ChatChecks,
    _HostResolutionChecks,
    _KeyValidationChecks,
    SimpleTestCase,
):
    def tearDown(self):
        reset_gateway()
