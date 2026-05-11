from pathlib import Path
import requests
import base64
import json
from .mloader_base import SpeechToTextModel
from dotenv import load_dotenv
import os

from logging_config import logger

class OpenRouterWhisper(SpeechToTextModel):
    def __init__(self):
        self.model_name: str = "openai/whisper-1"
        self.language: str = "pl"
        self.api_key = None
        self.load_model()

    def load_model(self):
        logger.info("🔌 Laczenie z API OpenRouter...")
        load_dotenv()
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            self.api_key = os.getenv('OPENAI_KEY')


    def load_processor(self):
        pass

    def transcribe(self, audio_path) -> dict:
        logger.info('Audio processing via OpenRouter...')

        if isinstance(audio_path, str):
            audio_path = Path(audio_path)

        if not self.api_key:
            raise RuntimeError("API key not loaded. Call load_model() first.")

        with open(audio_path, "rb") as f:
            base64_audio = base64.b64encode(f.read()).decode("utf-8")

        response = requests.post(
            url="https://openrouter.ai/api/v1/audio/transcriptions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            data=json.dumps({
                "model": self.model_name,
                "input_audio": {"data": base64_audio, "format": "wav"}, # OpenRouter expects 'input_audio' as an object
                "language": self.language,
                "response_format": "text"
            })
        )

        if response.status_code == 200:
            result = response.json()
            logger.info('Audio processed!')
            return {"text": result.get("text", "")}
        else:
            logger.error(f"Error from OpenRouter: {response.status_code} - {response.text}")
            return {"text": ""}
