import os


def llm_api_config() -> tuple[str | None, str]:
    api_key = (
        os.getenv("OPENROUTER_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("OPENAI_KEY")
    )
    url = (
        "https://openrouter.ai/api/v1/chat/completions"
        if os.getenv("OPENROUTER_API_KEY")
        else "https://api.openai.com/v1/chat/completions"
    )
    return api_key, url
