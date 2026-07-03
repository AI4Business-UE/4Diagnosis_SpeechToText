import qdrant_client.models as models

from app_stt.pipeline.stages.rag.encoder_models.encoders import SentenceEncoder
from app_stt.pipeline.data.macro_descs import MACRO_DESCS
from .client import get_qdrant_client, QdrantClientMode
from .config import MACRO_DESCS_COLLECTION
from ..fts import prepare_fts_text

def index_database(client_mode: QdrantClientMode, dense_encoder: SentenceEncoder, sparse_encoder: SentenceEncoder, distance: models.Distance, 
                   sparse_modifier: models.Modifier.IDF):
    client = get_qdrant_client(client_mode)
    
    client.create_collection(
        MACRO_DESCS_COLLECTION,
        vectors_config={
            "dense": models.VectorParams(
                size = dense_encoder.get_output_size(),
                distance=distance,
            )
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(modifier = sparse_modifier)
        }
    )
    
    templates = MACRO_DESCS['descriptions']
    lematized_templates = [prepare_fts_text(templ) for templ in templates]
    
    sparse_vectors = sparse_encoder.encode_templates(lematized_templates)
    dense_vectors = dense_encoder.encode_templates(templates)
    
    points = []
    for idx, (sparse_v, dense_v) in enumerate(zip(sparse_vectors, dense_vectors)):
        points.append(models.PointStruct(
            id = idx,
            vector = {
                "sparse": models.SparseVector(
                    indices = sparse_v.indices,
                    values = sparse_v.values
                ),
                "dense": dense_v.tolist()
            },
            payload = {
                "text": templates[idx]
            }
        ))
        
    client.upsert(MACRO_DESCS_COLLECTION, points)