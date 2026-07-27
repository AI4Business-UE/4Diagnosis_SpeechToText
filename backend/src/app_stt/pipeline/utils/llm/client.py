import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

_client: OpenAI | None = None


def get_llm_client() -> OpenAI:
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