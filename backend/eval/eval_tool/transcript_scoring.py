from __future__ import annotations

import unicodedata
from collections.abc import Iterable


def normalize_transcript(text: str) -> str:
    """Normalize casing, punctuation, and whitespace without transliterating."""
    normalized = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in text.lower()
    )
    return " ".join(normalized.split())


def score_transcript(reference: str, hypothesis: str) -> dict[str, int | float | None]:
    """Return per-sample WER/CER counts and rates for a reference/hypothesis pair."""
    normalized_reference = normalize_transcript(reference)
    normalized_hypothesis = normalize_transcript(hypothesis)

    reference_words = normalized_reference.split()
    hypothesis_words = normalized_hypothesis.split()
    word_errors = _edit_distance(reference_words, hypothesis_words)

    reference_characters = list(normalized_reference)
    hypothesis_characters = list(normalized_hypothesis)
    character_errors = _edit_distance(reference_characters, hypothesis_characters)

    return {
        "word_errors": word_errors,
        "reference_words": len(reference_words),
        "wer": _rate(word_errors, len(reference_words), len(hypothesis_words)),
        "character_errors": character_errors,
        "reference_characters": len(reference_characters),
        "cer": _rate(
            character_errors,
            len(reference_characters),
            len(hypothesis_characters),
        ),
    }


def aggregate_transcript_scores(
    scores: Iterable[dict[str, int | float | None]],
) -> dict[str, int | float | None]:
    """Pool edit counts and reference lengths rather than averaging sample rates."""
    rows = list(scores)
    word_errors = sum(int(row["word_errors"]) for row in rows)
    reference_words = sum(int(row["reference_words"]) for row in rows)
    character_errors = sum(int(row["character_errors"]) for row in rows)
    reference_characters = sum(int(row["reference_characters"]) for row in rows)

    wer = word_errors / reference_words if reference_words else (0.0 if rows and not word_errors else None)
    cer = (
        character_errors / reference_characters
        if reference_characters
        else (0.0 if rows and not character_errors else None)
    )

    return {
        "samples": len(rows),
        "word_errors": word_errors,
        "reference_words": reference_words,
        "wer": wer,
        "character_errors": character_errors,
        "reference_characters": reference_characters,
        "cer": cer,
    }


def _rate(errors: int, reference_size: int, hypothesis_size: int) -> float | None:
    if reference_size:
        return errors / reference_size
    return 0.0 if hypothesis_size == 0 else None


def _edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    """Compute Levenshtein distance with memory proportional to the shorter input."""
    if len(reference) < len(hypothesis):
        reference, hypothesis = hypothesis, reference

    previous = list(range(len(hypothesis) + 1))
    for ref_index, ref_item in enumerate(reference, start=1):
        current = [ref_index]
        for hyp_index, hyp_item in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[hyp_index] + 1,
                    previous[hyp_index - 1] + (ref_item != hyp_item),
                )
            )
        previous = current
    return previous[-1]
