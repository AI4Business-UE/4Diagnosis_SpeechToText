from pathlib import Path
import librosa
from scipy.io import wavfile
import torch

from .mloader_base import SpeechToTextModel
from dotenv import load_dotenv
import os

from elevenlabs.client import ElevenLabs


class ElevenLabsModel(SpeechToTextModel):
    def __init__(self):
        from app_stt.services.logger import get_logger
        logger = get_logger(__name__)
        self.model_name: str = "openai/whisper-small"
        self.language: str = "pl"
        logger.info("Initializing ElevanLabs model...")
        self.model = self.load_model()
        # self.processor = self.load_processor()

    def load_model(self):
        logger.info("Loading ElevanLabs model ...")
        load_dotenv()
        self.key = os.getenv("ELEVENLABS_KEY")
        return ElevenLabs(api_key = self.key)

    def load_processor(self):
        return ElevenLabs(api_key = self.key)

    def transcribe(self, audio_path) -> dict:
        """
        Transcribe audio file and return result in the format expected by transcriber.py
        """
        logger.info('Audio processing...')
        # Convert to Path if it's a string
        if isinstance(audio_path, str):
            audio_path = Path(audio_path)

        audio, sr = librosa.load(audio_path, sr=16000)

        input_audio = torch.tensor(audio)

        transcription = self.model.speech_to_text.convert(
            file=input_audio,
            model_id="scribe_v1",  # Model to use, for now only "scribe_v1" is supported
            tag_audio_events=False,  # Tag audio events like laughter, applause, etc.
            language_code="pol",
            # Language of the audio file. If set to None, the model will detect the language automatically.
            diarize=False,  # Whether to annotate who is speaking
        )

        logger.info("Audio processed!")
        return transcription # "text": transcription
