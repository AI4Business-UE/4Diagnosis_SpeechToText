import pytest
import numpy as np

from fastembed import SparseEmbedding
import qdrant_client.models as models

from app_stt.pipeline.stages.ner.entities import Component, Lesion, FluidSample, ComponentExtraction, LesionExtraction, FluidSampleExtraction
from app_stt.pipeline import PipelineConfig
from .. import encoder_models
from ..qdrant import indexing
from ..qdrant.client import QdrantClientMode
from ..qdrant.retriever import QdrantRetriever
from ..encoder_models.base import SentenceEncoder

@pytest.fixture
def component_extraction():
    return [Component(**c) for c in [
        {
            "name": "materiał",
            "dim_x": 5.5,
            "dim_y": 4.5,
            "dim_z": 3.0,
            "unit": "cm"
        }
    ]]

@pytest.fixture
def lesion_extraction():
    return [Lesion(**l) for l in [
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
    ]]
    
@pytest.fixture
def fluid_extraction():
    return []

@pytest.fixture(scope="session")
def monkeysession(): 
    with pytest.MonkeyPatch.context() as mp:
        yield mp

@pytest.fixture(scope="session")
def dense_encoder(monkeysession):
    def return_mock(_):
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
    
    monkeysession.setattr(indexing, "get_dense_encoder", return_mock)

@pytest.fixture(scope="session")
def sparse_encoder(monkeysession):
    def return_mock(_):
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
    monkeysession.setattr(indexing, "get_sparse_encoder", return_mock)

@pytest.fixture(scope="session")
def test_db_config(sparse_encoder, dense_encoder):
    return PipelineConfig(qdrant_client_mode=QdrantClientMode.IN_MEMORY)

@pytest.fixture(scope="session")
def db_index(test_db_config):
    indexing.index_database(test_db_config) 

def test_retrieval(db_index, test_db_config, component_extraction, lesion_extraction, fluid_extraction):
    retriever = QdrantRetriever(test_db_config) 
    results = retriever.retrieve_fusion(component_extraction, lesion_extraction, fluid_extraction, 5, models.Fusion.DBSF)
    
    assert len(results) > 0