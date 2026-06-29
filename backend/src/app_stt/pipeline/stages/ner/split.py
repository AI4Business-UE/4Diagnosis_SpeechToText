from .base import NERStrategy, ExtractionResult
from .extractor import extract
from .entities.patient import Patient, PatientExtraction, PATIENT_PROMPT
from .entities.component import Component, ComponentExtraction, COMPONENT_PROMPT
from .entities.lesion import Lesion, LesionExtraction, LESION_SPLIT_PROMPT
from .entities.fluid_sample import FluidSample, FluidSampleExtraction, FLUID_SAMPLE_PROMPT


class SplitNERStrategy(NERStrategy):
    """
    All four extractors run independently on the raw transcript.
    Faster, but Lesion extraction has no knowledge of which components exist,
    so component_index is never filled.
    """

    def __init__(self, model: str = "openai/gpt-4o"):
        self.model = model

    def extract(self, transcript: str) -> ExtractionResult:
        p_dict, _, _, _ = extract(transcript, PATIENT_PROMPT, PatientExtraction, self.model)
        c_dict, _, _, _ = extract(transcript, COMPONENT_PROMPT, ComponentExtraction, self.model)
        l_dict, _, _, _ = extract(transcript, LESION_SPLIT_PROMPT, LesionExtraction, self.model)
        f_dict, _, _, _ = extract(transcript, FLUID_SAMPLE_PROMPT, FluidSampleExtraction, self.model)

        return ExtractionResult(
            patient=Patient(**p_dict.get("patient", {})),
            components=[Component(**c) for c in c_dict.get("components", [])],
            lesions=[Lesion(**l) for l in l_dict.get("lesions", [])],
            fluid_samples=[FluidSample(**f) for f in f_dict.get("fluid_samples", [])],
        )
