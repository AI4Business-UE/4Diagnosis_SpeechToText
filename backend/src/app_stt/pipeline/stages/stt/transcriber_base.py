from abc import ABC, abstractmethod


class TranscriberBase(ABC):
    LANGUAGE = "pl"
    
    @abstractmethod
    def transcribe(self, audio_path: str) -> str:
        pass