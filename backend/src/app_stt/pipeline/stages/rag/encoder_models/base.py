from abc import ABC, abstractmethod
from typing import List

import torch

class SentenceEncoder(ABC):
    @abstractmethod
    def encode_templates(self, templates: List[str]) -> torch.Tensor:
        pass
    
    @abstractmethod
    def encode_queries(self, queries: List[str]) -> torch.Tensor:
        pass
    
    @abstractmethod
    def get_output_size(self) -> int:
        pass
    
    
class CrossReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, templates: List[str], top_k: int):
        pass