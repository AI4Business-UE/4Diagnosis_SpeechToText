from .whisper_base import WhisperBase
from ..llm.client import get_llm_client


class WhisperHosted(WhisperBase):
    def __init__(self, model_id: str):
        self._model_id = model_id
    
    def transcribe(self, audio_path):
        client = get_llm_client()
        with open(audio_path, 'rb') as f:
            result = client.audio.transcriptions.create(
                model=self._model_id,
                language=self.LANGUAGE,
                temperature=0,
                file=f
            )
            
        return result.text