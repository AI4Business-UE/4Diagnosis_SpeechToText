from pathlib import Path
from .mloader_base import SpeechToTextModel
from logging_config import logger


class WhisperLocal(SpeechToTextModel):
    def __init__(self, model_id: str = "openai/whisper-small"):
        self.model_name: str = model_id
        self.language: str = "pl"
        self._processor = None
        self._model = None
        self._forced_ids = None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        from transformers import WhisperForConditionalGeneration, WhisperProcessor
        logger.info(f"Loading Whisper model ({self.model_name})...")
        self._processor = WhisperProcessor.from_pretrained(self.model_name)
        self._model = WhisperForConditionalGeneration.from_pretrained(self.model_name)
        self._forced_ids = self._processor.get_decoder_prompt_ids(
            language=self.language, task="transcribe"
        )
        self._model.eval()
        logger.info(f"Whisper model ({self.model_name}) loaded.")

    def load_model(self):
        self._ensure_loaded()
        return self._model

    def load_processor(self):
        self._ensure_loaded()
        return self._processor

    def transcribe(self, audio_path) -> dict:
        import torch
        import librosa

        self._ensure_loaded()
        logger.info("Audio processing")

        if isinstance(audio_path, str):
            audio_path = Path(audio_path)

        audio, _ = librosa.load(audio_path, sr=16000)
        input_audio = torch.tensor(audio)

        inputs = self._processor(
            input_audio,
            sampling_rate=16000,
            return_tensors="pt",
            return_attention_mask=True,
        )

        with torch.no_grad():
            predicted_ids = self._model.generate(
                inputs["input_features"],
                attention_mask=inputs["attention_mask"],
                forced_decoder_ids=self._forced_ids,
            )

        transcription = self._processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
        logger.info("Audio processed successfully.")
        return {"text": transcription}
