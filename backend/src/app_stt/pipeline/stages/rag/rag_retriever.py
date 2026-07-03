from abc import ABC, abstractmethod
from typing import List, Literal

import qdrant_client.models as models

from app_stt.pipeline.stages.ner.entities import Component, Lesion, FluidSample 

class RAGRetriever(ABC):
    @abstractmethod
    def retrieve_fusion(self, 
                 components: List[Component],
                 lesions: List[Lesion],
                 fluids: List[FluidSample],
                 top_k: int,
                 fusion_type: models.Fusion,
                 weights_on: bool):
        pass 