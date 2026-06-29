from .factories import STTFactory, TTTFactory
from pathlib import Path
from logging_config import logger


class Transcriber:
    def __init__(self):
        self.model_loader_stt = STTFactory.get_model_loader()
        self.model_loader_ttt = None

    def turn_stt_on(self):
        logger.info("[Transcriber] Loading STT model...")
        try:
            self.turn_ttt_off()
            self.model_loader_stt = STTFactory.get_model_loader()
            if self.model_loader_stt:
                logger.info("[Transcriber] STT ready")
            else:
                logger.error("[Transcriber] Failed to load STT model")
        except Exception as e:
            logger.error(f"[Transcriber] STT load error: {e}")
            self.model_loader_stt = None

    def turn_stt_off(self):
        self.model_loader_stt = None

    def turn_ttt_on(self):
        logger.info("[Transcriber] Loading TTT model...")
        self.turn_stt_off()
        self.model_loader_ttt = TTTFactory.get_model_loader()
        logger.info("[Transcriber] TTT ready")

    def turn_ttt_off(self):
        self.model_loader_ttt = None


transcriber = Transcriber()


def transcribe_audio_chunk(audio_path: str) -> str:
    if not transcriber.model_loader_stt:
        transcriber.turn_stt_on()

    if not transcriber.model_loader_stt:
        logger.error("[Transcriber] STT model unavailable")
        return ""

    audio_file_path = Path(audio_path)
    wav_path = audio_file_path if audio_file_path.suffix.lower() == ".wav" else audio_file_path

    result = transcriber.model_loader_stt.transcribe(wav_path)
    text = result.get("text", "")
    logger.info(f"[Transcriber] Chunk transcribed: {text[:80]}")
    return text


def correct_full_transcription(full_text: str) -> str:
    if not full_text.strip():
        return full_text

    try:
        transcriber.turn_ttt_on()

        if transcriber.model_loader_ttt is None:
            logger.error("[Transcriber] TTT model unavailable — returning raw text")
            transcriber.turn_stt_on()
            return full_text

        logger.info(f"[Transcriber] Correcting transcription ({len(full_text)} chars)...")
        corrected = transcriber.model_loader_ttt.make_out_of_the_box_adjusting(full_text)
        logger.info("[Transcriber] Correction done")
        transcriber.turn_stt_on()
        return corrected

    except Exception as e:
        logger.error(f"[Transcriber] Correction failed: {e}")
        transcriber.turn_stt_on()
        return full_text
