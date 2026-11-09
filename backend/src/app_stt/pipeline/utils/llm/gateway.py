"""LLM gateway — jedyne miejsce, w którym wybierany jest Host (OpenRouter / OpenAI)
i gdzie formułowane są żądania do modelu.

Etapy pipeline'u używają kanonicznych referencji Modelu w formacie
`vendor/model`; Host wybierany jest przy deploymentu zmienną środowiskową
`LLM_HOST` (domyślnie `openrouter`) i nigdy nie jest odgadywany na podstawie
obecności kluczy API.
"""

import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from openai.types.audio import Transcription

load_dotenv()

OPENROUTER_HOST = "openrouter"
OPENAI_HOST = "openai"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

#: Host → nazwa zmiennej środowiskowej z kluczem API wymaganym przez ten Host.
_HOST_API_KEYS = {
    OPENROUTER_HOST: "OPENROUTER_API_KEY",
    OPENAI_HOST: "OPENAI_API_KEY",
}


def active_host() -> str:
    """Rozstrzyga aktywnego Hosta na podstawie zmiennej `LLM_HOST`.

    Pusty string traktowany jest jak brak wartości — domyślnym Hostem jest
    OpenRouter. Nieznana wartość (literówka typu `openai-direct`) jest
    odrzucana, aby nie zmieniać zachowania po cichu.
    """
    value = (os.getenv("LLM_HOST") or "").strip().lower()
    if not value:
        return OPENROUTER_HOST
    if value not in _HOST_API_KEYS:
        raise ValueError(
            f"Nieznana wartość LLM_HOST: '{value}'. "
            "Dozwolone wartości: 'openrouter', 'openai'."
        )
    return value


def _host_api_key(host: str) -> str:
    """Zwraca klucz API wymagany przez Host lub podnosi błąd konfiguracyjny."""
    key = os.getenv(_HOST_API_KEYS[host])
    if not key:
        raise ValueError(
            f"Brak klucza API Hosta '{host}'. "
            f"Ustaw {_HOST_API_KEYS[host]} w pliku .env albo wybierz inny Host "
            "zmienną LLM_HOST."
        )
    return key


def is_configured() -> bool:
    """Czy aktywny Host ma skonfigurowany klucz API (bez tworzenia klienta)."""
    return bool(os.getenv(_HOST_API_KEYS[active_host()]))


class LLMGateway:
    """Brama LLM — rozwiązuje referencje Modelu i nadaje żądaniom kształt
    właściwy dla aktywnego Hosta. Nigdy nie waliduje referencji przy
    konstrukcji (leniwa walidacja w momencie żądania)."""

    def __init__(self, client: OpenAI, host: str):
        if host not in _HOST_API_KEYS:
            raise ValueError(
                f"Nieznany Host: '{host}'. Dozwolone wartości: "
                f"{', '.join(sorted(_HOST_API_KEYS))}."
            )
        self.client = client
        self.host = host

    def resolve_model_ref(self, model_ref: str) -> str:
        """Rozwiązuje kanoniczną referencję Modelu (`vendor/model`) dla Hosta.

        OpenRouter serwuje referencje bez zmian. OpenAI obsługuje wyłącznie
        vendor `openai` — prefiks jest zdejmowany; każda inna referencja
        przerywa żądanie z błędem konfiguracyjnym.
        """
        if self.host == OPENROUTER_HOST:
            return model_ref
        vendor, separator, native_id = model_ref.partition("/")
        if not separator or vendor != OPENAI_HOST:
            raise ValueError(
                f"Host OpenAI nie obsługuje referencji Modelu '{model_ref}'. "
                "Na Hoście OpenAI dostępne są tylko modele 'openai/*' — "
                "zmień referencję modelu albo ustaw LLM_HOST='openrouter'."
            )
        return native_id

    def transcribe(
        self,
        audio_path: str,
        model_ref: str,
        *,
        keywords: list[str] | None = None,
        languages: list[str] | None = None,
        prompt: str | None = None,
        temperature: float | None = None,
    ) -> Transcription:
        """Transkrybuje plik audio u aktywnego Hosta.

        Etapy przekazują wyłącznie politykę domenową (słowa kluczowe, języki,
        kontekst promptu); kształt żądania — JSON z base64 audio i envelope
        `provider.options` dla OpenRouter albo multipart z płaskimi polami
        dla OpenAI — jest sprawą bramy.
        """
        resolved_model = self.resolve_model_ref(model_ref)
        if self.host == OPENROUTER_HOST:
            return self._transcribe_openrouter(
                audio_path, model_ref, resolved_model,
                keywords, languages, prompt, temperature,
            )
        return self._transcribe_openai(
            audio_path, resolved_model,
            keywords, languages, prompt, temperature,
        )

    def _transcribe_openrouter(self, audio_path, model_ref, resolved_model,
                               keywords, languages, prompt, temperature) -> Transcription:
        with open(audio_path, "rb") as audio_file:
            audio_data = base64.b64encode(audio_file.read()).decode("ascii")

        body: dict = {
            "model": resolved_model,
            "input_audio": {
                "data": audio_data,
                "format": Path(audio_path).suffix.lstrip(".").lower(),
            },
        }
        options: dict = {}
        if keywords is not None:
            options["keywords"] = list(keywords)
        if languages is not None:
            options["languages"] = list(languages)
        if prompt is not None:
            options["prompt"] = prompt
        if options:
            vendor = model_ref.partition("/")[0] or "openai"
            body["provider"] = {"options": {vendor: options}}
        if temperature is not None:
            body["temperature"] = temperature

        return self.client.post(
            "/audio/transcriptions",
            cast_to=Transcription,
            body=body,
        )

    def _transcribe_openai(self, audio_path, resolved_model,
                           keywords, languages, prompt, temperature) -> Transcription:
        kwargs: dict = {"model": resolved_model}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if prompt is not None:
            kwargs["prompt"] = prompt
        # `keywords`/`languages` są w pełni obsługiwane przez gpt-transcribe,
        # ale nie mają jeszcze własnych parametrów w SDK — jadą jako płaskie
        # pola body.
        extra_body: dict = {}
        if keywords is not None:
            extra_body["keywords"] = list(keywords)
        if languages is not None:
            extra_body["languages"] = list(languages)
        if extra_body:
            kwargs["extra_body"] = extra_body

        with open(audio_path, "rb") as audio_file:
            return self.client.audio.transcriptions.create(file=audio_file, **kwargs)

    def chat(
        self,
        model_ref: str,
        messages: list[dict],
        *,
        temperature: float | None = None,
        response_format: dict | None = None,
    ):
        """Wysyła żądanie czatu do aktywnego Hosta.

        Kształt żądania czatu jest wspólny dla obu Hostów — różni się jedynie
        rozwiązywanie referencji Modelu.
        """
        kwargs: dict = {"model": self.resolve_model_ref(model_ref), "messages": messages}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if response_format is not None:
            kwargs["response_format"] = response_format
        return self.client.chat.completions.create(**kwargs)


_gateway: LLMGateway | None = None


def get_gateway() -> LLMGateway:
    """Singletowa brama dla aktywnego Hosta. Walidacja Hosta i klucza jest
    eager — błąd konfiguracyjny pojawia się przy pierwszym użyciu, nie
    w środku przesyłania żądania."""
    global _gateway
    if _gateway is None:
        host = active_host()
        key = _host_api_key(host)
        if host == OPENROUTER_HOST:
            client = OpenAI(api_key=key, base_url=OPENROUTER_BASE_URL)
        else:
            client = OpenAI(api_key=key)
        _gateway = LLMGateway(client=client, host=host)
    return _gateway


def reset_gateway() -> None:
    """Rozbraja singlet — do użycia w testach i przy zmianie konfiguracji."""
    global _gateway
    _gateway = None
