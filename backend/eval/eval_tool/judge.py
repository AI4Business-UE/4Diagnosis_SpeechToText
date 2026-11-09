from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from statistics import mean
from typing import Any

_ISSUE_FIELDS = ("omissions", "additions", "contradictions")

_SYSTEM_PROMPT = """You are evaluating fidelity in a Polish medical transcription pipeline.
Compare the corrected transcript only with the supplied reference transcript. Do not
make an independent medical judgment and do not add facts from outside the reference.

Score fidelity from 0 to 4:
4: all reference information is preserved, with no unsupported additions.
3: largely faithful; only minor details are omitted or added.
2: partially faithful, but a material detail is omitted or added.
1: mostly unfaithful, with major omissions, additions, or contradictions.
0: unrelated, empty, or wholly contradictory to the reference.

Return only a JSON object with integer `score`, arrays of concise strings named
`omissions`, `additions`, and `contradictions`, and a concise `rationale`. A stylistic
rewrite or equivalent wording is not an error when meaning is preserved.

Ignore if `corrected_transcript` does not contain patient data (name, age, PESEL) but it appears in `reference`.
It is intended behavior, `corrected_transcript` should only contain specimen description.
"""


def evaluate_fidelity(
    reference_text: str,
    corrected_transcript: str,
    model: str,
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    """Ask a configured LLM to judge corrected-text fidelity against the reference."""
    if not model.strip():
        raise ValueError("A judge model must be explicitly configured")
    if client is None:
        from app_stt.pipeline.utils.llm.client import get_llm_client

        client = get_llm_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {"reference": reference_text, "corrected_transcript": corrected_transcript},
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not isinstance(content, str):
        raise ValueError("Judge returned an empty response")
    return parse_judgement(content)


def parse_judgement(content: str) -> dict[str, Any]:
    """Validate the structured result returned by the judge model."""
    try:
        result = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("Judge response is not valid JSON") from error
    if not isinstance(result, dict):
        raise ValueError("Judge response must be a JSON object")

    score = result.get("score")
    if isinstance(score, bool) or not isinstance(score, int) or score not in range(5):
        raise ValueError("Judge score must be an integer from 0–4")
    for field in _ISSUE_FIELDS:
        values = result.get(field)
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise ValueError(f"Judge field '{field}' must be an array of strings")
    rationale = result.get("rationale")
    if not isinstance(rationale, str):
        raise ValueError("Judge field 'rationale' must be a string")
    return {
        "score": score,
        **{field: result[field] for field in _ISSUE_FIELDS},
        "rationale": rationale,
    }


def aggregate_judgements(results: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(results)
    distribution = Counter(str(row["score"]) for row in rows)
    return {
        "samples": len(rows),
        "mean_score": round(mean(row["score"] for row in rows), 3) if rows else None,
        "score_distribution": {str(score): distribution[str(score)] for score in range(5)},
        "samples_with_omissions": sum(bool(row["omissions"]) for row in rows),
        "samples_with_additions": sum(bool(row["additions"]) for row in rows),
        "samples_with_contradictions": sum(bool(row["contradictions"]) for row in rows),
    }
