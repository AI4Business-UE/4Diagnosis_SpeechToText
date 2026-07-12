from __future__ import annotations

import re
import string


PUNCT_TRANSLATION = str.maketrans({char: " " for char in string.punctuation})
NUMBER_PATTERN = re.compile(r"\d+(?:[,.]\d+)?")
DIMENSION_PATTERN = re.compile(
    r"\d+(?:[,.]\d+)?(?:\s*[x×]\s*\d+(?:[,.]\d+)?)+\s*(?:mm|cm|m)?|"
    r"\d+(?:[,.]\d+)?\s*(?:mm|cm|m)"
)


def normalize_text(text: str) -> str:
    text = str(text or "").lower()
    text = text.replace("×", "x")
    text = text.translate(PUNCT_TRANSLATION)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _edit_distance(left: list[str] | str, right: list[str] | str) -> int:
    left_len = len(left)
    right_len = len(right)

    previous = list(range(right_len + 1))
    for i in range(1, left_len + 1):
        current = [i] + [0] * right_len
        for j in range(1, right_len + 1):
            substitution_cost = 0 if left[i - 1] == right[j - 1] else 1
            current[j] = min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + substitution_cost,
            )
        previous = current

    return previous[right_len]


def wer(reference: str, hypothesis: str) -> float:
    ref_words = normalize_text(reference).split()
    hyp_words = normalize_text(hypothesis).split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    return _edit_distance(ref_words, hyp_words) / len(ref_words)


def cer(reference: str, hypothesis: str) -> float:
    ref_chars = normalize_text(reference).replace(" ", "")
    hyp_chars = normalize_text(hypothesis).replace(" ", "")
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    return _edit_distance(ref_chars, hyp_chars) / len(ref_chars)


def _canonical_values(pattern: re.Pattern[str], text: str) -> list[str]:
    values = []
    for match in pattern.findall(str(text or "").lower()):
        value = re.sub(r"\s+", "", match)
        values.append(value.replace(",", ".").replace("×", "x"))
    return values


def recall(reference_values: list[str], hypothesis_values: list[str]) -> float | None:
    if not reference_values:
        return None

    remaining = list(hypothesis_values)
    matched = 0
    for value in reference_values:
        if value in remaining:
            matched += 1
            remaining.remove(value)

    return matched / len(reference_values)


def number_recall(reference: str, hypothesis: str) -> float | None:
    return recall(
        _canonical_values(NUMBER_PATTERN, reference),
        _canonical_values(NUMBER_PATTERN, hypothesis),
    )


def dimension_recall(reference: str, hypothesis: str) -> float | None:
    return recall(
        _canonical_values(DIMENSION_PATTERN, reference),
        _canonical_values(DIMENSION_PATTERN, hypothesis),
    )


def compute_stt_metrics(reference: str, hypothesis: str) -> dict[str, float | None]:
    return {
        "wer": wer(reference, hypothesis),
        "cer": cer(reference, hypothesis),
        "number_recall": number_recall(reference, hypothesis),
        "dimension_recall": dimension_recall(reference, hypothesis),
    }


def _self_check() -> None:
    assert wer("guz 3 cm", "guz 3 cm") == 0
    assert cer("guz 3 cm", "guz 3 cm") == 0
    assert number_recall("guz 3 cm i 4 cm", "guz 3 cm i 40 cm") == 0.5


if __name__ == "__main__":
    _self_check()
    print("STT metrics self-check passed")
