from abc import ABC, abstractmethod

class SpeechToTextModel(ABC):
    @abstractmethod
    def load_model(self):
        pass

    @abstractmethod
    def load_processor(self):
        pass

    @abstractmethod
    def transcribe(self, audio_path):
        """Transcribe audio file and return result dict with 'text' key"""
        pass