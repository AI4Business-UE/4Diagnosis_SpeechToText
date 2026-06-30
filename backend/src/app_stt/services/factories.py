from ..config import STT_MODEL, TTT_MODEL, WHISPER_MODELS, DEFAULT_WHISPER_MODEL


class STTFactory:
    @staticmethod
    def get_model_loader(whisper_model_key: str = DEFAULT_WHISPER_MODEL):
        try:
            if STT_MODEL == "local/whisper":
                from .models_loaders.stt.mloader_whisper_local import WhisperLocal
                model_id = WHISPER_MODELS.get(whisper_model_key, WHISPER_MODELS[DEFAULT_WHISPER_MODEL])
                return WhisperLocal(model_id=model_id)
            elif STT_MODEL == "OpenAI/whisper":
                from .models_loaders.stt.mloader_openai_whisper import OpenAIWhisper
                return OpenAIWhisper()
            elif STT_MODEL == "OpenRouter/whisper":
                from .models_loaders.stt.mloader_openrouter_whisper import OpenRouterWhisper
                return OpenRouterWhisper()
            else:
                raise ValueError(f"Nieznany typ modelu: {STT_MODEL}")
        except Exception as e:
            print(f"Błąd podczas ładowania modelu STT: {str(e)}")
            return None


class TTTFactory:
    @staticmethod
    def get_model_loader():
        try:
            if TTT_MODEL == "Local/BielikAI":
                from .models_loaders.ttt.mloader_bielik import Bielik
                return Bielik()
            elif TTT_MODEL == "Local/Pllum":
                from .models_loaders.ttt.mloader_pllum import PLLuM
                return PLLuM()
            elif TTT_MODEL == "OpenRouter/GPT":
                from .models_loaders.ttt.mloader_openrouter_gpt import OpenRouterGPT
                return OpenRouterGPT()
            elif TTT_MODEL == "OpenAI/GPT":
                from .models_loaders.ttt.mloader_openai_gpt import OpenAIGPT
                return OpenAIGPT()
            elif TTT_MODEL == "disabled":
                return None
            else:
                raise ValueError(f"Nieznany typ modelu: {TTT_MODEL}")
        except Exception as e:
            print(f"Błąd podczas ładowania modelu TTT: {str(e)}")
            return None
