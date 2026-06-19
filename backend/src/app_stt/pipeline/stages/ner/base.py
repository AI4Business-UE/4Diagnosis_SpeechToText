from abc import ABC, abstractmethod
from typing import List

from pydantic import BaseModel, Field

from .entities.patient import Patient
from .entities.component import Component
from .entities.lesion import Lesion
from .entities.fluid_sample import FluidSample


class ExtractionResult(BaseModel):
    patient: Patient = Field(default_factory=Patient)
    components: List[Component] = Field(default_factory=list)
    lesions: List[Lesion] = Field(default_factory=list)
    fluid_samples: List[FluidSample] = Field(default_factory=list)


class NERStrategy(ABC):
    @abstractmethod
    def extract(self, transcript: str) -> ExtractionResult:
        """Extract medical entities from a transcript string."""
        pass
