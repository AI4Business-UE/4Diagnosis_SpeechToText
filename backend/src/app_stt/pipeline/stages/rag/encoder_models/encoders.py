from sentence_transformers import SentenceTransformer
from fastembed import SparseTextEmbedding

from app_stt.pipeline.stages.rag.encoder_models.base import SentenceEncoder

_dense_encoder = None
_sparse_encoder = None
 
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
        pass
    
    
def get_dense_encoder(model: str) -> SentenceEncoder:
    global _dense_encoder
    
    if _dense_encoder is not None:
        if _dense_encoder._model_name != model:
            raise RuntimeError(f"Dense encoder already intiialized with '{_dense_encoder.model_name}', requested '{model}'")
        
        return _dense_encoder
    
    if model == "intfloat/multilingual-e5-large":
        _dense_encoder = E5Large()
        return _dense_encoder
    
    raise RuntimeError(f"Invalid dense encoder model '{model}', valid options: 'intfloat/multilingual-e5-large'")

def get_sparse_encoder(model: str) -> SentenceEncoder:
    global _sparse_encoder
    
    if _sparse_encoder is not None:
        if _sparse_encoder._model_name != model:
            raise RuntimeError(f"Sparse encoder already intiialized with '{_sparse_encoder.model_name}', requested '{model}'")
        
        return _sparse_encoder
    
    if model == "Qdrant/bm25":
        _sparse_encoder = FastEmbedSparse()
        return _sparse_encoder
    
    raise RuntimeError(f"Invalid sparse encoder model '{model}', valid options: 'Qdrant/bm25'")
