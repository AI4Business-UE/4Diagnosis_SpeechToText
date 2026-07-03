import qdrant_client.models as models
from typing import List

from .client import get_qdrant_client, QdrantClientMode 
from .queries import detect_specimen_type, build_queries, SearchQuery
from .config import MACRO_DESCS_COLLECTION
from ..fts import prepare_fts_text
from ..encoder_models.base import SentenceEncoder
from ..rag_retriever import RAGRetriever

class QdrantRetriever(RAGRetriever):
    def __init__(self, dense_encoder: SentenceEncoder, sparse_encoder: SentenceEncoder, client_mode: QdrantClientMode):
        self._client = get_qdrant_client(client_mode)
        self._dense_encoder = dense_encoder
        self._sparse_encoder = sparse_encoder
    
    def retrieve_fusion(self, components, lesions, fluids, top_k: int, fusion_type: models.Fusion, weights_on: bool):
        s_type = detect_specimen_type(components, lesions, fluids) 
        queries = build_queries(components, lesions, fluids, s_type)
        prefetches = self._build_prefetch(queries, top_k)
        
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