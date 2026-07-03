from dataclasses import dataclass, field
from typing import ClassVar


WHISPER_MODELS: dict[str, str] = {
    "whisper-small": "openai/whisper-small",
    "whisper-medium": "openai/whisper-medium",
    "whisper-medical-pl": "msxksm/whisper-medium-medical-pl",
    "whisper-large-v3": "openai/whisper-large-v3",
}

import qdrant_client.models as qdrant_models

from .stages.rag.qdrant.client import QdrantClientMode
from .stages.rag.encoder_models.base import SentenceEncoder
from .stages.rag.encoder_models.encoders import E5Large, FastEmbedSparse

@dataclass
class PipelineConfig:
    # ── STT ──────────────────────────────────────────────────────────────────
    # whisper_local | openai_whisper | openrouter_whisper
    stt_model: str = "whisper_local"

    # HuggingFace model ID for local whisper
    # choices: whisper-small, whisper-medium, whisper-medical-pl, whisper-large-v3
    whisper_model: str = "whisper-small"

    WHISPER_MODELS: ClassVar[dict[str, str]] = WHISPER_MODELS

    @property
    def whisper_hf_id(self) -> str:
        return WHISPER_MODELS[self.whisper_model]

    # ── NER ──────────────────────────────────────────────────────────────────
    # chained: Patient → Component → Lesion (z kontekstem komponentów) → FluidSample
    # split:   wszystkie cztery ekstrakcje niezależnie na surowym transkrypcie
    ner_strategy: str = "chained"

    # model przekazywany do OpenRouter (lub OpenAI)
    llm_model: str = "openai/gpt-4o"

    # ── RAG ────────────────────────────────────────────────────
    vector_db_provider: str = "qdrant"
    dense_encoder_model: str = "intfloat/multilingual-e5-large"
    sparse_encoder_model: str = "Qdrant/bm25"
    top_k_results: int = 5
    qdrant_fusion_type: qdrant_models.Fusion = qdrant_models.Fusion.DBSF
    qdrant_distance_metric: qdrant_models.Distance = qdrant_models.Distance.COSINE
    qdrant_client_mode: QdrantClientMode = QdrantClientMode.IN_MEMORY
    qdrant_sparse_modifier: qdrant_models.Modifier = qdrant_models.Modifier.IDF
    
    # ── Preprocessing ────────────────────────────────────────────────────────
    target_sr: int = 16000
    use_volume_normalization: bool = True
    use_bandpass_filter: bool = False
    use_noise_reduction: bool = False
    use_vad: bool = False
    use_salt_augmentation: bool = False

    volume_target_peak: float = 0.95
    high_pass_hz: int = 200
    low_pass_hz: int = 7900
    filter_order: int = 4

    noise_reduction_stationary: bool = False
    noise_reduction_prop_decrease: float = 0.8

    vad_threshold: float = 0.5
    vad_min_speech_duration_ms: int = 250
    vad_min_silence_duration_ms: int = 100
    vad_speech_pad_ms: int = 200

    preprocessing_output_dir: str = "./preprocessed_audio"
