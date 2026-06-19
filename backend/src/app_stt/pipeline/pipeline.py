from __future__ import annotations

import os

from .config import PipelineConfig
from .stages.preprocessing import AudioPreprocessor
from .stages.stt.whisper_local import WhisperSmall
from .stages.ner.base import NERStrategy
from .stages.ner.split import SplitNERStrategy
from .stages.ner.chained import ChainedNERStrategy


class Pipeline:
    """
    Full medical transcription pipeline:
      1. Preprocessing  — normalise, filter, denoise, VAD
      2. STT            — Whisper (local or API)
      3. NER            — extract Patient, Components, Lesions, FluidSamples
      4. RAG            — (in progress)
      5. Template fill  — (in progress)

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
        """
        preprocessing_meta = self.preprocessor.process(audio_path)

        stt_result = self.stt.transcribe(preprocessing_meta["output_path"])
        transcript = self._get_text(stt_result)

        entities = self.ner.extract(transcript)

        return {
            "transcript": transcript,
            "entities": entities.model_dump(),
            "preprocessing": preprocessing_meta,
        }

    # ── private ───────────────────────────────────────────────────────────────

    def _build_stt(self):
        model = self.config.stt_model
        if model == "whisper_local":
            return WhisperSmall()
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
            return ChainedNERStrategy(self.config.llm_model)
        if strategy == "split":
            return SplitNERStrategy(self.config.llm_model)
        raise ValueError(
            f"Unknown NER strategy '{strategy}'. Supported: 'chained', 'split'."
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
