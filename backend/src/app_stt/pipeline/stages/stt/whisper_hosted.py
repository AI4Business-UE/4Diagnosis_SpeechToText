from .transcriber_base import TranscriberBase
from app_stt.pipeline.utils.llm.gateway import get_gateway


class WhisperHosted(TranscriberBase):
    """Transkrypcja modelem Hosta (OpenRouter / OpenAI) przez bramę LLM.

    `model_ref` jest kanoniczną referencją Modelu (`vendor/model`) — to brama
    rozstrzyga, jak Host ją serwuje. Etap nie zna Hosta.
    """

    def __init__(self, model_ref: str, gateway=None):
        self._model_ref = model_ref
        self._gateway = gateway

    def transcribe(self, audio_path):
        gateway = self._gateway if self._gateway is not None else get_gateway()

        result = gateway.transcribe(
            audio_path,
            self._model_ref,
            languages=[self.LANGUAGE],
            temperature=0,
        )

        return result.text
