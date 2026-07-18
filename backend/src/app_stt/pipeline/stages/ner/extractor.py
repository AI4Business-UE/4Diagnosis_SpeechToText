import os
import json
import time

from pydantic import ValidationError

from app_stt.pipeline.stages.llm.client import get_llm_client


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
    client = get_llm_client()
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
