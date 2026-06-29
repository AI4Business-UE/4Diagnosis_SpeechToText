import os
import json
import time

from openai import OpenAI
from dotenv import load_dotenv
from pydantic import ValidationError

load_dotenv()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """
    Build LLM client — tries keys in order:
      1. OPENROUTER_API_KEY  → OpenRouter (openrouter.ai)
      2. OPENAI_API_KEY      → OpenAI directly
    Raises RuntimeError if neither is set.
    """
    global _client
    if _client is not None:
        return _client

    key = os.getenv("OPENROUTER_API_KEY")
    if key:
        _client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
        return _client

    key = os.getenv("OPENAI_API_KEY")
    if key:
        _client = OpenAI(api_key=key)
        return _client

    raise RuntimeError(
        "Brak klucza API. Ustaw OPENROUTER_API_KEY lub OPENAI_API_KEY w pliku .env. "
        "Jeśli nie masz klucza, pipeline użyje TTT fallback (stary serwis TTT)."
    )


def _strip_empty_and_none(data):
    if isinstance(data, dict):
        cleaned = {k: _strip_empty_and_none(v) for k, v in data.items()}
        return {k: v for k, v in cleaned.items() if v not in (None, {}, [])}
    if isinstance(data, list):
        cleaned = [_strip_empty_and_none(item) for item in data]
        return [item for item in cleaned if item not in (None, {}, [])]
    return data


def extract(transcript: str, prompt: str, schema, model: str = "openai/gpt-4o"):
    """
    Send transcript + prompt to LLM, validate against Pydantic schema.

    Returns
    -------
    result_dict : dict
        Validated and serialized result, or raw cleaned dict on validation failure.
    duration : float
        Request duration in seconds.
    tokens : dict
        prompt_tokens, completion_tokens, total_tokens.
    validation_errors : list
        Pydantic validation errors (empty if validation passed).
    """
    client = _get_client()
    start = time.perf_counter()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": transcript},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    duration = time.perf_counter() - start

    tokens = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }

    raw = response.choices[0].message.content
    parsed = json.loads(raw)

    result_dict = None
    validation_errors = []

    try:
        validated = schema.model_validate(parsed)
        result_dict = validated.model_dump(exclude_defaults=True)
    except ValidationError as err:
        validation_errors = err.errors()
        result_dict = _strip_empty_and_none(parsed)

    return result_dict, duration, tokens, validation_errors
