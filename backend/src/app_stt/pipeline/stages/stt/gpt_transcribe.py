import base64
from pathlib import Path

from openai.types.audio.transcription import Transcription

from .transcriber_base import TranscriberBase
from app_stt.pipeline.utils.llm.client import get_llm_client
from app_stt.models import Keyword


PATHOLOGY_PROMPT = (
    "Nagranie badania patomorfologicznego w języku polskim. Lekarz mówiący może okazjonalnie się poprawiać, "
    "np. poprawnie 'torbielowaty, nie, litowy', zamiast 'torbielowaty, nielitowy.'"
)


class GPTTranscribe(TranscriberBase):
    def transcribe(self, audio_path):
        client = get_llm_client()
        with open(audio_path, "rb") as audio_file:
            audio_data = base64.b64encode(audio_file.read()).decode("ascii")

        result = client.post(
            "/audio/transcriptions",
            cast_to=Transcription,
            body={
                "model": "openai/gpt-transcribe",
                "input_audio": {
                    "data": audio_data,
                    "format": Path(audio_path).suffix.lstrip(".").lower(),
                },
                "provider": {
                    "options": {
                        "openai": {
                            "keywords": list(Keyword.objects.values_list("text", flat=True)),
                            "languages": ["pl"],
                            "prompt": PATHOLOGY_PROMPT,
                        }
                    }
                },
            },
        )

        return result.text
