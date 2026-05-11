from pathlib import Path
from openai import OpenAI

from .mloader_base import SpeechToTextModel
from dotenv import load_dotenv
import os

class OpenAIWhisper(SpeechToTextModel):
    def __init__(self):
        self.model_name: str = "whisper-1"
        self.language: str = "pl"
        self.model = self.load_model()
        # self.processor = self.load_processor()
        self.api_key = None

    def load_model(self):
        print("🔌 Łączenie z API OpenAI...")
        load_dotenv()
        self.api_key = os.getenv('OPENAI_KEY')
        return OpenAI(api_key=self.api_key)

    def load_processor(self):
        pass

    def transcribe(self, audio_path) -> dict:
        print('Audio processing...')

        # Convert to Path if it's a string
        if isinstance(audio_path, str):
            audio_path = Path(audio_path)

        if not self.model:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        audio_path = Path(audio_path)
        with open(audio_path, "rb") as audio_file:
            response = self.model.audio.transcriptions.create(
                model=self.model_name,
                file=audio_file,
                language=self.language,
                response_format="text"
            )
        print('Audio processed!')
        return {"text": response}
