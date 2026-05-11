from transformers import WhisperForConditionalGeneration, WhisperProcessor
from pathlib import Path
import librosa
from scipy.io import wavfile
import torch

from transformers import AutoModel
from .mloader_base import SpeechToTextModel
from logging_config import logger

class WhisperLocal(SpeechToTextModel):
    def __init__(self):
        self.model_name: str = "openai/whisper-small"
        self.language: str = "pl"
        self.processor = self.load_processor()
        self.model = self.load_model()
        self.forced_ids = self.processor.get_decoder_prompt_ids(language=self.language, task="transcribe")
        self.model.eval()

    def load_model(self):
        logger.info("Loading Whisper model...")
        try:
            model = WhisperForConditionalGeneration.from_pretrained(self.model_name)
            logger.info("Whisper model loaded successfully.")
            return model
        except Exception as e:
            logger.error(f"Error while loading Whisper model: {e}")
        

    def load_processor(self):
        logger.info("Loading Whisper process...")
        try:
            process = WhisperProcessor.from_pretrained(self.model_name)
            logger.info("Whisper process loaded successfully.")
            return process
        except Exception as e:
            logger.error(f"Error while loading Whisper model: {e}")


    def transcribe(self, audio_path) -> dict:
        """
        Transcribe audio file and return result in the format expected by transcriber.py
        """
        print("Audio processing")
        logger.info("Audio processing")
        # Convert to Path if it's a string
        if isinstance(audio_path, str):
            audio_path = Path(audio_path)

        audio, sr = librosa.load(audio_path, sr=16000)

        input_audio = torch.tensor(audio)

        inputs = self.processor(
            input_audio,
            sampling_rate=16000,
            return_tensors="pt",
            return_attention_mask=True
        )

        with torch.no_grad():
            predicted_ids = self.model.generate(
                inputs["input_features"],
                attention_mask=inputs["attention_mask"],
                forced_decoder_ids=self.forced_ids
            )

        transcription = self.processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
        logger.info("Success: Audio processed!")
        return {"text": transcription}
