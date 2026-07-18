from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ..ner import ExtractionResult


class Answerer(ABC):
    @abstractmethod
    def correct_transcription(
        self, 
        transcript: str, 
        templates: List[str], 
        ner_extraction: ExtractionResult
    ) -> str:
        pass