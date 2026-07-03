from __future__ import annotations

import qdrant_client.models as models
from typing import List, TYPE_CHECKING

from .client import get_qdrant_client 
from .queries import build_queries, SearchQuery
from .config import MACRO_DESCS_COLLECTION
from ..encoder_models import get_sparse_encoder, get_dense_encoder
from ..fts import prepare_fts_text
from ..rag_retriever import RAGRetriever

if TYPE_CHECKING:
    from app_stt.pipeline.config import PipelineConfig

class QdrantRetriever(RAGRetriever):
    def __init__(self, config: PipelineConfig):
        self._client = get_qdrant_client(config.qdrant_client_mode)
        self._dense_encoder = get_dense_encoder(config.dense_encoder_model)
        self._sparse_encoder = get_sparse_encoder(config.sparse_encoder_model)
    
    def retrieve_fusion(self, components, lesions, fluids, top_k: int, fusion_type: models.Fusion):
        queries = build_queries(components, lesions, fluids)
        prefetches = self._build_prefetch(queries, top_k)
        
        if not prefetches:
            return []
        
        results = self._client.query_points(
            MACRO_DESCS_COLLECTION,
            prefetch=prefetches,
            limit=top_k,
            query=models.FusionQuery(fusion=fusion_type),
            with_payload=True
        )
         
        return self._extract_templates_from_points(results.points)
     
    def _extract_templates_from_points(self, points: List[models.ScoredPoint]):
        return [p.payload.get('text') for p in points]
    
    def _build_prefetch(self, search_queries: List[SearchQuery], top_k: int, query_filter: models.Filter = models.Filter()) -> List[models.Prefetch]:
        prefetches = []

        dense_texts = [sq.text for sq in search_queries if sq.using in ["dense", "both"]]
        sparse_texts = [prepare_fts_text(sq.text) for sq in search_queries if sq.using in ["sparse", "both"]]
        
        dense_vectors = self._dense_encoder.encode_queries(dense_texts) if dense_texts else []
        sparse_vectors = self._sparse_encoder.encode_queries(sparse_texts) if sparse_texts else []

        dense_idx = 0
        sparse_idx = 0
        for sq in search_queries:
            if sq.using in ["dense", "both"]:
                q_vec = dense_vectors[dense_idx]
                prefetches.append(models.Prefetch(
                    query=q_vec.tolist() if hasattr(q_vec, "tolist") else q_vec,
                    using="dense",
                    limit=top_k,
                    filter=query_filter
                ))
                dense_idx += 1

            if sq.using in ["sparse", "both"]:
                s_vec = sparse_vectors[sparse_idx]
                if hasattr(s_vec, "indices") and hasattr(s_vec, "values"):
                    query_vector = models.SparseVector(
                        indices=s_vec.indices.tolist() if hasattr(s_vec.indices, "tolist") else s_vec.indices,
                        values=s_vec.values.tolist() if hasattr(s_vec.values, "tolist") else s_vec.values
                    )
                else:
                    query_vector = s_vec
                prefetches.append(models.Prefetch(
                    query=query_vector,
                    using="sparse",
                    limit=top_k,
                    filter=query_filter
                ))
                sparse_idx += 1

        return prefetches    