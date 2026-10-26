import json

from .transcriber_base import TranscriberBase
from app_stt.pipeline.utils.llm.client import get_llm_client
from app_stt.data.medical_keywords import MEDICAL_KEYWORDS


class GPTTranscribe(TranscriberBase):
    def transcribe(self, audio_path):
        client = get_llm_client()
        with open(audio_path, 'rb') as f:
            result = client.audio.transcriptions.create(
                model="gpt-transcribe",
                file=f,
                prompt="Nagranie badania patomorfologicznego w języku polskim. Lekarz mówiący może okazjonalnie się poprawiać, np. poprawnie 'torbielowaty, nie, litowy', zamiast 'torbielowaty, nielitowy.'",
                extra_body={
                    "keywords": MEDICAL_KEYWORDS,
                    "languages": ["pl"]
                }
            )
            
        return result.text