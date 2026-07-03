import pytest
import numpy as np

from fastembed import SparseEmbedding
import qdrant_client.models as models

from app_stt.pipeline.stages.ner.entities import Component, Lesion, FluidSample, ComponentExtraction, LesionExtraction, FluidSampleExtraction
from ..qdrant.client import QdrantClientMode
from ..qdrant.retriever import QdrantRetriever
from ..qdrant.indexing import index_database
from ..encoder_models.base import SentenceEncoder
from app_stt.pipeline.stages.rag.encoder_models.encoders import E5Large, FastEmbedSparse

@pytest.fixture
def component_extraction():
    return ComponentExtraction(components=[Component(**c) for c in [
        {
            "name": "materiał",
            "dim_x": 5.5,
            "dim_y": 4.5,
            "dim_z": 3.0,
            "unit": "cm"
        }
    ]])

@pytest.fixture
def lesion_extraction():
    return LesionExtraction(lesions=[Lesion(**l) for l in [
        {
            "type": "guz",
            "dim_x": 5.5,
            "dim_y": 4.5,
            "dim_z": 3.0,
            "component_index": 0
        },
        {
            "type": "guz",
            "dim_x": 3.5,
            "dim_y": 3.0,
            "dim_z": 3.5,
            "color": "żółtej",
            "features": [
                "wylewy_krwawe"
            ],
            "component_index": 0
        }
    ]])
    
@pytest.fixture
def fluid_extraction():
    return FluidSampleExtraction(fluid_samples=[])

@pytest.fixture(scope="session")
def dense_encoder():
    class MockDenseEncoder(SentenceEncoder):
        def encode_queries(self, queries):
            return [
                np.random.random(1024),
                np.random.random(1024),
                np.random.random(1024)
            ]
        
        def encode_templates(self, templates):
            return [
                np.random.random(1024),
                np.random.random(1024),
                np.random.random(1024)
            ]
        
        def get_output_size(self):
            return 1024
    
    return MockDenseEncoder()

@pytest.fixture(scope="session")
def sparse_encoder():
    class MockSparseEncoder(SentenceEncoder):
        def encode_queries(self, queries):
            return [
                SparseEmbedding(
                    indices=np.array([101, 102]),
                    values=np.random.random(2)
                ),
            ]
            
        def encode_templates(self, templates):
            return [
                SparseEmbedding(
                    indices=np.array([406, 407, 501]),
                    values=np.random.random(3)
                )
            ]
        
        def get_output_size(self):
            return None
        
    return MockSparseEncoder()

@pytest.fixture(scope="session")
def test_db_config(dense_encoder, sparse_encoder):
    return {
        "client_mode": QdrantClientMode.IN_MEMORY,
        "dense_encoder": dense_encoder,
        "sparse_encoder": sparse_encoder,
        "distance": models.Distance.COSINE,
        "sparse_modifier": models.Modifier.IDF
    }

@pytest.fixture(scope="session")
def db_index(test_db_config):
    index_database(**test_db_config) 

@pytest.mark.integration
def test_retrieval(db_index, dense_encoder, sparse_encoder, component_extraction, lesion_extraction, fluid_extraction):
    retriever = QdrantRetriever(dense_encoder, sparse_encoder, QdrantClientMode.IN_MEMORY) 
    results = retriever.retrieve_fusion(component_extraction, lesion_extraction, fluid_extraction, 5, models.Fusion.DBSF, False)
    
    assert len(results) > 0