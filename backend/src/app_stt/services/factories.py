from ..config import STT_MODEL, TTT_MODEL

from .models_loaders.stt.mloader_base import SpeechToTextModel
from .models_loaders.ttt.mloader_base import TextToTextModel

from .models_loaders.stt.mloader_whisper_local import WhisperLocal
# from .models_loaders.stt.mloader_eleven_labs import ElevenLabsModel
from .models_loaders.stt.mloader_openai_whisper import OpenAIWhisper
from .models_loaders.stt.mloader_openrouter_whisper import OpenRouterWhisper

from .models_loaders.ttt.mloader_bielik import Bielik
from .models_loaders.ttt.mloader_pllum import PLLuM
from .models_loaders.ttt.mloader_openrouter_gpt import OpenRouterGPT
from .models_loaders.ttt.mloader_openai_gpt import OpenAIGPT

class STTFactory:
    @staticmethod
    def get_model_loader() -> SpeechToTextModel:
        try:
            if STT_MODEL == "local/whisper":
                return WhisperLocal()
            elif STT_MODEL == "OpenAI/whisper":
                return OpenAIWhisper()
            elif STT_MODEL == "OpenRouter/whisper":
                return OpenRouterWhisper()
            # elif STT_MODEL == 'ElevenLabs':
            #     return ElevenLabsModel()
            else:
                raise ValueError(f"Nieznany typ modelu: {STT_MODEL}")
        except Exception as e:
            print(f"Błąd podczas ładowania modelu STT: {str(e)}")
            # Preferably, we'd want to return a lightweight fallback model here instead of None
            # but for now, we'll return None and handle it in the calling code
            return None


class TTTFactory:
    @staticmethod
    def get_model_loader() -> TextToTextModel:
        try:
            if TTT_MODEL == "Local/BielikAI":
                return Bielik()
            elif TTT_MODEL == "Local/Pllum":
                return PLLuM()
            elif TTT_MODEL == 'OpenRouter/GPT':
                return OpenRouterGPT()
            elif TTT_MODEL == 'OpenAI/GPT':
                return OpenAIGPT()
            elif TTT_MODEL == "disabled":
                return None  # Zwracamy None gdy TTT jest wyłączony
            else:
                raise ValueError(f"Nieznany typ modelu: {TTT_MODEL}")
        except Exception as e:
            print(f"Błąd podczas ładowania modelu TTT: {str(e)}")
            # Returning None allows the system to continue without the correction model
            return None
