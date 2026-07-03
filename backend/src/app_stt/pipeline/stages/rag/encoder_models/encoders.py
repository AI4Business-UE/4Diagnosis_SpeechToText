from sentence_transformers import SentenceTransformer
from fastembed import SparseTextEmbedding

from app_stt.pipeline.stages.rag.encoder_models.base import SentenceEncoder


class E5Large(SentenceEncoder):
    _model_name = "intfloat/multilingual-e5-large"
    
    def __init__(self):
        self._model = SentenceTransformer(self._model_name)
        self._model_kwargs = { "normalize_embeddings": True, "show_progress_bar": False }
    
    def encode_templates(self, templates):
        _tplts = [f"passage: {t}" for t in templates]
        
        return self._model.encode(_tplts, **self._model_kwargs)
    
    def encode_queries(self, queries):
        _queries = [f"query: {q}" for q in queries]
        
        return self._model.encode(_queries, **self._model_kwargs)
    
    def get_output_size(self):
        return self._model.get_embedding_dimension()
    
    
class FastEmbedSparse(SentenceEncoder):
    _model_name = "Qdrant/bm25"
    
    def __init__(self):
        self._model = SparseTextEmbedding(model_name=self._model_name)
        
    def encode_templates(self, templates):
        return list(self._model.embed(templates))
        
    def encode_queries(self, queries):
        return list(self._model.query_embed(queries))

    def get_output_size(self):
        # TODO: Add vector size output 
        return self._model