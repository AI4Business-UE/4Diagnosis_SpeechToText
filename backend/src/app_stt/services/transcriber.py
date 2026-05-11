from .factories import STTFactory, TTTFactory
from .models_loaders.utilities.out_of_the_box import OutOfTheBoxAdjuster

from logging import log

import subprocess
from pathlib import Path

from logging_config import logger

class Transcriber:
    def __init__(self):
        self.model_loader_stt = STTFactory.get_model_loader()
        self.model_loader_ttt = None

        # Ładuj model TTT tylko gdy potrzebny (dla korekty)
        self.model_ttt = None
        self.tokenizer_ttt = None
        self.ttt_loaded = False

    def turn_stt_on(self):
        logger.info("Turning speech-to-text on...")
        try:
            self.turn_ttt_off()
            self.model_loader_stt = STTFactory.get_model_loader()
            if self.model_loader_stt:
                logger.info("Speech-to-text turned on!")
            else:
                logger.error("Failed to turn on speech-to-text!")
        except Exception as e:
            logger.error(f"Error turning on STT: {str(e)}")
            self.model_loader_stt = None

    def turn_stt_off(self):
        self.model_loader_stt = None
        logger.info("Speech-to-text turned off!")

    def turn_ttt_on(self):
        logger.info("Turning text-to-text on...")
        self.turn_stt_off()
        self.model_loader_ttt = TTTFactory.get_model_loader()
        logger.info("Text-to-text turned on")

    def turn_ttt_off(self):
        self.model_loader_ttt = None
        logger.info("Text-to-text turned off!'")



transcriber = Transcriber()



def transcribe_audio_chunk(audio_path: str) -> str:
    """
    Transcribes an audio chunk file to text.

    Args:
        audio_path: Path to the audio file (WAV format expected, but will convert from WebM if needed)
        
    Returns:
        str: The transcribed text from the audio chunk
    """

    print('Starting chunk transcription...')

    # Make sure the STT model is loaded
    if not transcriber.model_loader_stt:
        transcriber.turn_stt_on()
        
    if not transcriber.model_loader_stt:
        logger.error("Failed to load the STT model!")
        return ""

    audio_file_path = Path(audio_path)
    if audio_file_path.suffix.lower() == '.wav':
        wav_path = audio_file_path
    else:
        print(audio_path)
    
    result = transcriber.model_loader_stt.transcribe(wav_path)
    transcribed_text = result.get("text", "")
    logger.info(f'The chunk transcribed: {transcribed_text}')

    return transcribed_text


def correct_full_transcription(full_text: str) -> str:
    """
    Korekta pełnej transkrypcji przy użyciu BielikAI

    Args:
        full_text: Pełny tekst do korekty

    Returns:
        Poprawiony tekst
    """
    print('Starting full transcription...')

    if not full_text.strip():
        return full_text

    try:
        transcriber.turn_ttt_on()

        # Get model and tokenizer from model_loader_ttt
        if transcriber.model_loader_ttt is None:
            logger.error("Model TTT failed to load - I return original text")
            transcriber.turn_stt_on()
            return full_text

        print(f'Robię korektę! {full_text}')
        corrected_text = transcriber.model_loader_ttt.make_out_of_the_box_adjusting(full_text)
        print(f"Korekta: '{full_text}' -> '{corrected_text}'")
        transcriber.turn_stt_on()
        return corrected_text

    except Exception as e:
        print(f"Błąd podczas korekty tekstu: {str(e)} - zwracam oryginalny tekst")
        transcriber.turn_stt_on()
        return full_text
