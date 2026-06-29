from pathlib import Path
import requests
import base64
import json
import os
from .mloader_base import SpeechToTextModel
from logging_config import logger


class OpenRouterWhisper(SpeechToTextModel):
    def __init__(self):
        self.model_name: str = "openai/whisper-1"
        self.language: str = "pl"
        self.api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_KEY")
        if not self.api_key:
            logger.error("[STT] OPENROUTER_API_KEY not set — transcription will fail")

    def load_model(self):
        pass

    def load_processor(self):
        pass

    def transcribe(self, audio_path) -> dict:
        logger.info("[STT] Transcribing via OpenRouter Whisper...")

        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set. Add it to backend/.env")

        if isinstance(audio_path, str):
            audio_path = Path(audio_path)

        with open(audio_path, "rb") as f:
            base64_audio = base64.b64encode(f.read()).decode("utf-8")

        response = requests.post(
            url="https://openrouter.ai/api/v1/audio/transcriptions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": self.model_name,
                "input_audio": {"data": base64_audio, "format": "wav"},
                "language": self.language,
                "response_format": "text",
            }),
        )

        if response.status_code == 200:
            result = response.json()
            logger.info("[STT] Transcription done")
            return {"text": result.get("text", "")}
        else:
            logger.error(f"[STT] OpenRouter error {response.status_code}: {response.text}")
            return {"text": ""}
