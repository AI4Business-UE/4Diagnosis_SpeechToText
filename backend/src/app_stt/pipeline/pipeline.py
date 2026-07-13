from __future__ import annotations

import os

from .config import PipelineConfig
from .stages.preprocessing import AudioPreprocessor
from .stages.stt.whisper_local import WhisperLocal
from .stages.ner.base import NERStrategy
from .stages.ner.split import SplitNERStrategy
from .stages.ner.chained import ChainedNERStrategy
from .stages.rag.rag_retriever import RAGRetriever
from .stages.rag.qdrant import QdrantRetriever
from .stages.answerer import Answerer, NoFillAnswerer


class Pipeline:
    """
    Full medical transcription pipeline:
      1. Preprocessing  — normalise, filter, denoise, VAD
      2. STT            — Whisper (local or API)
      3. NER            — extract Patient, Components, Lesions, FluidSamples
      4. RAG            — build queries from Components, Lesions, FluidSamples and query the templates db
      5. Answerer       - send transcript for correction using retrieved templates and NER data 

    Usage
    -----
    Minimal (all defaults):
        p = Pipeline()
        result = p.run("recording.wav")

    Custom config:
        cfg = PipelineConfig(ner_strategy="split", use_vad=True)
        p = Pipeline(cfg)
        result = p.run("recording.wav")

    Colab / Kaggle:
        from pipeline import Pipeline
        result = Pipeline().run("/content/sample.m4a")
    """

    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()
        self.preprocessor = AudioPreprocessor(self.config)
        self.stt = self._build_stt()
        self.ner = self._build_ner()
        self.rag = self._build_rag()
        self.answerer = self._build_answerer()

    @classmethod
    def from_config(cls, **overrides) -> Pipeline:
        """Create pipeline with default config, optionally overriding fields."""
        config = PipelineConfig(**overrides)
        return cls(config)

    def run(self, audio_path: str) -> dict:
        """
        Run the full pipeline on an audio file.

        Parameters
        ----------
        audio_path : str
            Path to the input audio file (wav, mp3, m4a, …).

        Returns
        -------
        dict with keys:
            transcript   – raw STT output string
            entities     – ExtractionResult as dict
            preprocessing – metadata dict from AudioPreprocessor
            retrieved_templates - templates retrieved from vector database
        """
        preprocessing_meta = self.preprocessor.process(audio_path)

        stt_result = self.stt.transcribe(preprocessing_meta["output_path"])
        transcript = self._get_text(stt_result)

        entities = self.ner.extract(transcript)
        templates = self.rag.retrieve_fusion(
            components=entities.components,
            lesions=entities.lesions,
            fluids=entities.fluid_samples,
            top_k=self.config.top_k_results,
            fusion_type=self.config.qdrant_fusion_type,
        )

        corrected_transcript = self.answerer.correct_transcription(
            transcript,
            templates,
            entities
        )

        return {
            "transcript": transcript,
            "entities": entities.model_dump(),
            "preprocessing": preprocessing_meta,
            "retrieved_templates": templates,
            "corrected_transcript": corrected_transcript
        }

    # ── private ───────────────────────────────────────────────────────────────

    def _build_stt(self):
        model = self.config.stt_model
        if model == "whisper_local":
            return WhisperLocal(
                model_id=self.config.whisper_hf_id,
                condition_on_prev_tokens=self.config.whisper_local_condition_on_prev_tokens,
                no_repeat_ngram_size=self.config.whisper_local_no_repeat_ngram_size
            )
        raise ValueError(
            f"Unknown STT model '{model}'. "
            "Supported: 'whisper_local'. "
            "OpenAI / OpenRouter variants coming soon."
        )

    def _build_ner(self) -> NERStrategy:
        if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
            print(
                "[Pipeline] Brak klucza API (OPENROUTER_API_KEY / OPENAI_API_KEY). "
                "Używam TTT fallback — stary serwis korekty tekstu."
            )
            from .stages.ner.ttt_fallback import TTTFallbackStrategy
            return TTTFallbackStrategy()

        strategy = self.config.ner_strategy
        if strategy == "chained":
            return ChainedNERStrategy(self.config.ner_llm_model)
        if strategy == "split":
            return SplitNERStrategy(self.config.ner_llm_model)
        raise ValueError(
            f"Unknown NER strategy '{strategy}'. Supported: 'chained', 'split'."
        )
        
    def _build_rag(self) -> RAGRetriever:
        provider = self.config.vector_db_provider
        if provider == 'qdrant':
            return QdrantRetriever(self.config)

        raise ValueError(
            f"Unknown vector db provider '{provider}'. Supported: 'qdrant'."
        )
    
    def _build_answerer(self) -> Answerer:
        strategy = self.config.answerer_strategy
        if strategy == 'no-fill':
            return NoFillAnswerer(self.config.answerer_llm_model)
        
        raise ValueError(
            f"Unknown answerer strategy '{strategy}'. Supported: 'no-fill'."
        )
        
    @staticmethod
    def _get_text(stt_result: dict | str) -> str:
        if isinstance(stt_result, str):
            return stt_result
        if "text" in stt_result:
            return stt_result["text"]
        # HuggingFace pipeline with return_timestamps=True returns chunks
        chunks = stt_result.get("chunks", [])
        return " ".join(c.get("text", "") for c in chunks).strip()
