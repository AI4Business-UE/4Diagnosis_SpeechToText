from __future__ import annotations

import torch
import librosa
from transformers import WhisperForConditionalGeneration, WhisperProcessor, pipeline

from .whisper_base import WhisperBase

class WhisperLocal(WhisperBase):
    """
    Local Whisper STT model via HuggingFace Transformers.

    Uses the pipeline API with chunk_length_s=30 so long recordings
    are handled correctly without manual chunking.
    """

    def __init__(
        self, 
        model_id: str = "openai/whisper-small",
        condition_on_prev_tokens: bool = False,
        no_repeat_ngram_size: int = 3 
        ):
        self.model_id = model_id
        self._condition_on_prev_tokens = condition_on_prev_tokens
        self._no_repeat_ngram_size = no_repeat_ngram_size
        
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.processor = self._load_processor()
        self.model = self._load_model()
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=self.model,
            tokenizer=self.processor.tokenizer,
            feature_extractor=self.processor.feature_extractor,
            chunk_length_s=30,
            device=self.device,
        )
        self.model.eval()

    def transcribe(self, audio_path: str) -> dict:
        audio, sr = librosa.load(audio_path, sr=16000)
        result = self.pipe(
            {"array": audio, "sampling_rate": sr},
            generate_kwargs={
                "language": self.LANGUAGE, 
                "task": "transcribe",
                "condition_on_prev_tokens": self._condition_on_prev_tokens,
                "no_repeat_ngram_size": self._no_repeat_ngram_size
            },
            return_timestamps=True,
        )
        return result

    def _load_model(self) -> WhisperForConditionalGeneration:
        print(f"Loading Whisper model ({self.model_id})...")
        return WhisperForConditionalGeneration.from_pretrained(self.model_id)

    def _load_processor(self) -> WhisperProcessor:
        print(f"Loading Whisper processor ({self.model_id})...")
        return WhisperProcessor.from_pretrained(self.model_id)


# backward compat alias
WhisperSmall = WhisperLocal
