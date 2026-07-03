from sentence_transformers import CrossEncoder

from app_stt.pipeline.stages.rag.encoder_models.base import CrossReranker
    
    
class BGEReranker(CrossReranker):
    _model_name = "BAAI/bge-reranker-v2-m3"
    
    def __init__(self):
        self._model = CrossEncoder(self._model_name)
        
    def rerank(self, query, templates, top_k = 1):
        pairs = [[query, t] for t in templates]
        scores = self._model.predict(pairs).tolist()
        
        results = [{"template": t, "score": s} for t, s in zip(templates, scores)]
        results = sorted(results, key=lambda x: x["score"], reverse=True)
        
        return results[:top_k]