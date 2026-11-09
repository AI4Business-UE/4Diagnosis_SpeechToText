from .transcriber_base import TranscriberBase
from app_stt.pipeline.utils.llm.gateway import get_gateway
from app_stt.models import Keyword


PATHOLOGY_PROMPT = (
    "Nagranie badania patomorfologicznego w języku polskim. Lekarz mówiący może okazjonalnie się poprawiać, "
    "np. poprawnie 'torbielowaty, nie, litowy', zamiast 'torbielowaty, nielitowy.'"
)


class GPTTranscribe(TranscriberBase):
    """Transkrypcja patomorfologiczna przez bramę LLM.

    Etap deklaruje wyłącznie politykę domenową — słowa kluczowe z Keyword
    Catalog, język polski i prompt badania; kształt żądania właściwy
    aktywnemu Hostowi (OpenRouter / OpenAI) należy do bramy.
    """

    def __init__(self, model_ref: str, gateway=None):
        self._model_ref = model_ref
        self._gateway = gateway

    def transcribe(self, audio_path):
        gateway = self._gateway if self._gateway is not None else get_gateway()

        result = gateway.transcribe(
            audio_path,
            self._model_ref,
            keywords=list(Keyword.objects.values_list("text", flat=True)),
            languages=["pl"],
            prompt=PATHOLOGY_PROMPT,
        )

        return result.text
