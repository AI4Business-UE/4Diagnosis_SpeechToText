import enum
from functools import cache
from typing import Literal

from qdrant_client import QdrantClient 

_client = None

class QdrantClientMode(enum.Enum):
    IN_MEMORY = 'in_memory'
    CONNECTION = 'connection'

def get_qdrant_client(connection_string: str, mode: QdrantClientMode) -> QdrantClient:
    global _client
    
    if _client is not None:
        return _client
    
    if mode == QdrantClientMode.IN_MEMORY:
        _client = QdrantClient(":memory:")
        return _client
    
    if mode == QdrantClientMode.CONNECTION:
        _client = QdrantClient(connection_string)
        return _client
    
    raise RuntimeError(f'Unsupported qdrant client mode: {mode}')