import json

from .base import NERStrategy, ExtractionResult
from .extractor import extract
from .entities.patient import Patient, PatientExtraction, PATIENT_PROMPT
from .entities.component import Component, ComponentExtraction, COMPONENT_PROMPT
from .entities.lesion import Lesion, LesionExtraction, LESION_CHAINED_PROMPT
from .entities.fluid_sample import FluidSample, FluidSampleExtraction, FLUID_SAMPLE_PROMPT


class ChainedNERStrategy(NERStrategy):
    """
    Extractors run sequentially: Patient → Component → Lesion → FluidSample.
    Lesion extraction receives the previously extracted component names as
    context, which lets the model fill component_index reliably.
    """

    def __init__(self, model: str = "openai/gpt-4o"):
        self.model = model

    def extract(self, transcript: str) -> ExtractionResult:
        p_dict, _, _, _ = extract(transcript, PATIENT_PROMPT, PatientExtraction, self.model)
        c_dict, _, _, _ = extract(transcript, COMPONENT_PROMPT, ComponentExtraction, self.model)

        # Pass component names as context so Lesion can assign component_index
        component_names = [c.get("name", "") for c in c_dict.get("components", [])]
        lesion_prompt = LESION_CHAINED_PROMPT % json.dumps(component_names, ensure_ascii=False)
        l_dict, _, _, _ = extract(transcript, lesion_prompt, LesionExtraction, self.model)

        f_dict, _, _, _ = extract(transcript, FLUID_SAMPLE_PROMPT, FluidSampleExtraction, self.model)

        return ExtractionResult(
            patient=Patient(**p_dict.get("patient", {})),
            components=[Component(**c) for c in c_dict.get("components", [])],
            lesions=[Lesion(**l) for l in l_dict.get("lesions", [])],
            fluid_samples=[FluidSample(**f) for f in f_dict.get("fluid_samples", [])],
        )
