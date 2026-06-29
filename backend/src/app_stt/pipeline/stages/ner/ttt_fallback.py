"""
TTT fallback strategy — używana gdy nie ma żadnego klucza API (OPENROUTER ani OPENAI).
Wywołuje stary serwis correct_full_transcription() z app_stt.services.transcriber
i mapuje jego prosty wynik na ExtractionResult.

Stary TTT zwraca JSON:
  { analyzed_organ, name, surname, pesel, description }
"""

import json
import warnings

from .base import NERStrategy, ExtractionResult
from .entities.patient import Patient
from .entities.component import Component


class TTTFallbackStrategy(NERStrategy):
    """
    Fallback gdy brak OPENROUTER_API_KEY i OPENAI_API_KEY.
    Używa starego serwisu TTT (Bielik / PLLuM / OpenRouter / OpenAI)
    skonfigurowanego przez TTT_MODEL w app_stt/config.py.
    """

    def extract(self, transcript: str) -> ExtractionResult:
        try:
            raw = self._call_ttt(transcript)
            data = json.loads(raw)
            return self._map(data)
        except Exception as exc:
            warnings.warn(
                f"[TTTFallback] Nie udało się wywołać TTT: {exc}. "
                "Zwracam pusty wynik — ustaw OPENROUTER_API_KEY lub OPENAI_API_KEY "
                "żeby korzystać z pełnego NER.",
                stacklevel=2,
            )
            return ExtractionResult()

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _call_ttt(transcript: str) -> str:
        from app_stt.services.transcriber import correct_full_transcription
        return correct_full_transcription(transcript)

    @staticmethod
    def _map(data: dict) -> ExtractionResult:
        first_name = data.get("name") or None
        last_name = data.get("surname") or None
        pesel = data.get("pesel") or None
        organ = data.get("analyzed_organ") or None

        return ExtractionResult(
            patient=Patient(first_name=first_name, last_name=last_name, pesel=pesel),
            components=[Component(name=organ)] if organ else [],
        )
