"""Domain terms and field config used by deterministic sanity guardrails."""

LESION_WORDS = [
    "guz",
    "guza",
    "guzem",
    "torbiel",
    "torbieli",
    "polip",
    "polipa",
    "ognisko",
    "zmiana",
    "zmiany",
]

REQUIRED_FORM_FIELDS = ["organ", "name", "age", "pesel", "description"]

SANITY_ALLOWED_SEVERITIES = {"error", "warning", "info"}
