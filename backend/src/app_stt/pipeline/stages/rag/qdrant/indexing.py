from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import qdrant_client.models as models

from app_stt.pipeline.stages.rag.encoder_models.encoders import get_dense_encoder, get_sparse_encoder
from app_stt.data.macro_descriptions import MACRO_DESCS
from .client import get_qdrant_client
from ..fts import prepare_fts_text

if TYPE_CHECKING:
    from app_stt.pipeline import PipelineConfig

logger = logging.getLogger(__name__)

def index_database(cfg: PipelineConfig):
    logger.info(f"RAG: Preparing to index Qdrant database. Creating Qdrant '{cfg.qdrant_client_mode.name}' client...")
    client = get_qdrant_client(cfg.qdrant_connection_string, cfg.qdrant_client_mode)
    
    logger.info(f"RAG: Creating encoders...")
    dense_encoder = get_dense_encoder(cfg.dense_encoder_model)
    sparse_encoder = get_sparse_encoder(cfg.sparse_encoder_model)
    
    logger.info(f"RAG: Creating template collection in the database...")

    if client.collection_exists(collection_name=cfg.macro_descs_collection):
        logger.info(f"RAG: Collection already exists, deleting and replacing...")
        client.delete_collection(collection_name=cfg.macro_descs_collection)

    client.create_collection(
        cfg.macro_descs_collection,
        vectors_config={
            "dense": models.VectorParams(
                size = dense_encoder.get_output_size(),
                distance=cfg.qdrant_distance_metric,
            )
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(modifier = cfg.qdrant_sparse_modifier)
        }
    )
    
    templates = MACRO_DESCS['descriptions']
    
    logger.info(f"RAG: Building lemmatized templates for sparse vectors...")
    lematized_templates = [prepare_fts_text(templ) for templ in templates]
    
    logger.info(f"RAG: Encoding templates into vectors...") 
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
    
    logger.info(f"RAG: Inserting vectors into database...")      
    client.upsert(cfg.macro_descs_collection, points)
    logger.info(f"RAG: Indexing stage complete!")