from __future__ import annotations

import os
import logging

from .config import PipelineConfig
from .form_data import build_form_data_from_entities
from app_stt.services.data_sanity_check import run_data_sanity_check


logger = logging.getLogger(__name__)

_pipeline = None


def get_pipeline() -> Pipeline:
    global _pipeline
    
    if isinstance(_pipeline, Pipeline):
        return _pipeline

    _pipeline = Pipeline()

    return _pipeline


class Pipeline:
    """
    Full medical transcription pipeline:
      1. Preprocessing  — normalise, filter, denoise, VAD
      2. STT            — Whisper (local or API)
      3. NER            — extract Patient, Components, Lesions, FluidSamples
      4. RAG            — build queries from Components, Lesions, FluidSamples and query the templates db
      5. Answerer       - send transcript for correction using retrieved templates and NER data 
      6. Sanity         - run final guardrails on generated form data

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
        from .stages.preprocessing import AudioPreprocessor

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
    
    def run(self, audio_path: str, patient_metadata: dict | None = None) -> dict:
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
            form_data    - frontend form payload derived from entities and corrected transcript
            sanity_result - optional guardrail result, or None when disabled
        """
        logger.info("PIPELINE: Beginning audio preprocessing...")
        preprocessing_meta = self.preprocessor.process(audio_path)
        logger.info("PIPELINE: Audio prerocessed!")

        logger.info("PIPELINE: Beginning transcription...")
        stt_result = self.stt.transcribe(preprocessing_meta["output_path"])
        
        transcript = self._get_text(stt_result)
        logger.info(f"PIPELINE: Transcription finished: {transcript}")

        logger.info(f"PIPELINE: Beginning extraction...")
        entities = self.ner.extract(transcript)
        logger.info(f"PIPELINE: NER extraction finished: {entities}")
        
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
        entities_dict = entities.model_dump()
        form_data = build_form_data_from_entities(
            entities_dict,
            corrected_transcript,
            patient_metadata,
        )
        sanity_result = None
        if self.config.enable_sanity_check:
            sanity_result = run_data_sanity_check(
                corrected_transcript,
                form_data,
                mode=self.config.sanity_mode,
            )

        return {
            "transcript": transcript,
            "entities": entities_dict,
            "preprocessing": preprocessing_meta,
            "retrieved_templates": templates,
            "corrected_transcript": corrected_transcript,
            "form_data": form_data,
            "sanity_result": sanity_result,
        }

    # ── private ───────────────────────────────────────────────────────────────

    def _build_stt(self):
        from .stages.stt import WhisperLocal, WhisperHosted

        model = self.config.stt_model
        if model == "whisper_local":
            return WhisperLocal(
                model_id=self.config.whisper_hf_id,
                condition_on_prev_tokens=self.config.whisper_local_condition_on_prev_tokens,
                no_repeat_ngram_size=self.config.whisper_local_no_repeat_ngram_size
            )
        if model == "whisper_hosted":
            return WhisperHosted(
                model_id=self.config.whisper_hf_id
            )
        
        raise ValueError(
            f"Unknown STT model '{model}'. "
            "Supported: 'whisper_local', 'whisper_hosted. "
        )

    def _build_ner(self):
        if not os.getenv("OPENROUTER_API_KEY") and not os.getenv("OPENAI_API_KEY"):
            print(
                "[Pipeline] Brak klucza API (OPENROUTER_API_KEY / OPENAI_API_KEY). "
                "Używam TTT fallback — stary serwis korekty tekstu."
            )
            from .stages.ner.ttt_fallback import TTTFallbackStrategy
            return TTTFallbackStrategy()

        strategy = self.config.ner_strategy
        if strategy == "chained":
            from .stages.ner.chained import ChainedNERStrategy

            return ChainedNERStrategy(self.config.ner_llm_model)
        if strategy == "split":
            from .stages.ner.split import SplitNERStrategy

            return SplitNERStrategy(self.config.ner_llm_model)
        raise ValueError(
            f"Unknown NER strategy '{strategy}'. Supported: 'chained', 'split'."
        )
        
    def _build_rag(self):
        provider = self.config.vector_db_provider
        if provider == 'qdrant':
            from .stages.rag.qdrant import QdrantRetriever

            return QdrantRetriever(self.config)

        raise ValueError(
            f"Unknown vector db provider '{provider}'. Supported: 'qdrant'."
        )
    
    def _build_answerer(self):
        from .stages.answerer import NoFillAnswerer

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
