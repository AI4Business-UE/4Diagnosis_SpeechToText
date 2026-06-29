from dataclasses import dataclass, field


@dataclass
class PipelineConfig:
    # ── STT ──────────────────────────────────────────────────────────────────
    # whisper_local | openai_whisper | openrouter_whisper
    stt_model: str = "whisper_local"

    # ── NER ──────────────────────────────────────────────────────────────────
    # chained: Patient → Component → Lesion (z kontekstem komponentów) → FluidSample
    # split:   wszystkie cztery ekstrakcje niezależnie na surowym transkrypcie
    ner_strategy: str = "chained"

    # model przekazywany do OpenRouter (lub OpenAI)
    llm_model: str = "openai/gpt-4o"

    # ── RAG (in progress) ────────────────────────────────────────────────────
    # none | bm25 | faiss
    rag_variant: str = "none"

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
