import os
import base64
import asyncio
import tempfile
import json
import traceback
import struct
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from .transcriber import transcribe_audio_chunk, correct_full_transcription
from logging_config import logger

def create_wav_from_float32(float32_chunks, sample_rate=16000, filename=None):
    """
    Create WAV file from list of Float32Array chunks
    """
    # Combine all chunks into one array
    total_samples = sum(len(chunk) for chunk in float32_chunks)
    if total_samples == 0:
        raise ValueError("No audio data to write")

    combined_audio = []
    for chunk in float32_chunks:
        combined_audio.extend(chunk)

    # Convert float32 (-1.0 to 1.0) to int16 (-32768 to 32767)
    pcm_data = b''
    for sample in combined_audio:
        # Clamp to [-1.0, 1.0]
        sample = max(-1.0, min(1.0, sample))
        # Convert to 16-bit PCM
        pcm_sample = int(sample * 32767)
        pcm_data += struct.pack('<h', pcm_sample)

    # Create WAV header
    num_channels = 1
    bits_per_sample = 16
    bytes_per_sample = bits_per_sample // 8
    byte_rate = sample_rate * num_channels * bytes_per_sample
    block_align = num_channels * bytes_per_sample
    data_size = len(pcm_data)
    file_size = 36 + data_size

    header = b'RIFF'
    header += struct.pack('<I', file_size)
    header += b'WAVE'
    header += b'fmt '
    header += struct.pack('<I', 16)
    header += struct.pack('<H', 1)
    header += struct.pack('<H', num_channels)
    header += struct.pack('<I', sample_rate)
    header += struct.pack('<I', byte_rate)
    header += struct.pack('<H', block_align)
    header += struct.pack('<H', bits_per_sample)
    header += b'data'
    header += struct.pack('<I', data_size)

    wav_data = header + pcm_data

    if filename:
        with open(filename, 'wb') as f:
            f.write(wav_data)

    return wav_data

class AudioConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.audio_buffer = []  # Lista Float32Array chunks
        self.transcription_task = None
        self.full_transcription = ""  # Przechowuje pełną transkrypcję
        self.is_recording = True  # Flaga określająca czy nagrywanie trwa
        self.patient_metadata = {} # Przechowuje metadane pacjenta

        tmp_dir = os.path.join(os.getcwd(), "app_stt", "data", "tmp_audio")
        os.makedirs(tmp_dir, exist_ok=True)

        self.audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav", dir=tmp_dir)
        self.transcription_lock = asyncio.Lock()

    async def connect(self):
        logger.info("[WS] WebSocket connected")
        await self.accept()
        self.transcription_task = asyncio.create_task(self.process_buffer())

    async def disconnect(self, close_code):
        logger.error("[WS] WebSocket disconnected")
        if self.transcription_task:
            self.transcription_task.cancel()
        self.audio_file.flush()
        self.audio_file.close()

    async def receive(self, text_data=None, bytes_data=None):
        try:
            logger.info(f"[WS] Received data: {text_data[:100]}")
            msg = json.loads(text_data)

            if "control" in msg and msg["control"] == "stop_recording":
                logger.info("[CTRL] Stop recording signal received!")
                self.is_recording = False
                await self.finalize_transcription()
                return

            if "control" in msg and msg["control"] == "rewind":
                seconds = msg.get("seconds", 5)
                logger.info(f"[CTRL] Rewinding buffer by {seconds} seconds")
                await self.rewind_buffer(seconds)
                return

            # Handle metadata updates
            if msg.get("type") == "metadata" or msg.get("type") == "metadata_update":
                metadata = msg.get("metadata", {})
                if metadata:
                    self.patient_metadata.update(metadata)
                    logger.info(f"[METADATA] Updated patient metadata: {self.patient_metadata}")
                return

            # Handle recording start/end with metadata
            if msg.get("type") == "recording_start":
                metadata = msg.get("metadata", {})
                if metadata:
                    self.patient_metadata.update(metadata)
                    logger.info(f"[START] Recording started with metadata: {self.patient_metadata}")
                return
                
            if msg.get("type") == "recording_end":
                metadata = msg.get("metadata", {})
                if metadata:
                    self.patient_metadata.update(metadata)
                    logger.info(f"[END] Recording ended with metadata: {self.patient_metadata}")
                return

            if msg.get("type") == "audio_chunk" and msg.get("data"):
                logger.info("[AUDIO] Appending audio chunk")
                metadata = msg.get("metadata", {})
                if metadata:
                    self.patient_metadata.update(metadata)
                    logger.info(f"[AUDIO] Audio chunk with metadata: {self.patient_metadata}")

                audio_data = msg["data"]
                if isinstance(audio_data, dict) and 'data' in audio_data:
                    audio_b64 = audio_data['data']
                elif isinstance(audio_data, str):
                    audio_b64 = audio_data
                else:
                    logger.error(f"[ERROR] Unexpected audio data format: {type(audio_data)}")
                    return
                try:
                    audio_bytes = base64.b64decode(audio_b64)
                    num_samples = len(audio_bytes) // 4
                    audio_chunk = []
                    for i in range(num_samples):
                        sample_bytes = audio_bytes[i*4:(i+1)*4]
                        sample = struct.unpack('<f', sample_bytes)[0]  # little-endian float32
                        audio_chunk.append(sample)

                    self.audio_buffer.append(audio_chunk)
                    logger.info(f"[AUDIO] Added chunk with {len(audio_chunk)} samples")
                except Exception as e:
                    logger.error(f"[ERROR] Failed to decode audio chunk: {e}")
                    return
        except json.JSONDecodeError:
            if text_data:
                try:
                    logger.info("[AUDIO] Decoding raw base64 audio chunk")
                    audio_chunk = base64.b64decode(text_data)
                    self.audio_buffer.extend(audio_chunk)
                    self.audio_file.write(audio_chunk)
                except Exception:
                    print("[ERROR] Failed to decode raw base64 audio chunk")
        except Exception as e:
            logger.error(f"[ERROR] Exception in receive: {e}")
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": str(e)
            }))

    async def rewind_buffer(self, seconds: int):
        SAMPLE_RATE = 16000
        BYTES_PER_SECOND = SAMPLE_RATE * 2
        rewind_bytes = seconds * BYTES_PER_SECOND
        self.audio_buffer = self.audio_buffer[:-rewind_bytes] if len(self.audio_buffer) > rewind_bytes else bytearray()

    async def process_buffer(self):
        logger.info("[TRANSCRIBE] Starting buffer processing loop")
        while True:
            await asyncio.sleep(5)

            if not self.is_recording and not self.audio_buffer:
                logger.error("[TRANSCRIBE] Exiting loop (recording stopped and buffer empty)")
                break

            if self.audio_buffer:
                logger.info("[TRANSCRIBE] Processing audio buffer")

                # Create WAV file from Float32Array chunks
                create_wav_from_float32(self.audio_buffer, sample_rate=16000, filename=self.audio_file.name)
                self.audio_buffer.clear()
                audio_path = self.audio_file.name

                logger.info(f"[AUDIO] Created WAV file from chunks")

                async with self.transcription_lock:
                    try:
                        text = transcribe_audio_chunk(audio_path)
                        logger.info(f"[TRANSCRIBE] Raw transcription: {text}")

                        if text.strip():
                            # Dodaje tekst do pełnej transkrypcji jeśli jeszcze go tam nie ma
                            stripped_text = text.strip()
                            if stripped_text not in self.full_transcription:
                                if self.full_transcription:
                                    self.full_transcription += " " + stripped_text
                                else:
                                    self.full_transcription = stripped_text

                        await self.send(text_data=json.dumps({
                            "type": "transcript",
                            "text": text,
                            "interim": "",
                            "is_final": False
                        }))
                    except AttributeError as ae:
                        if "'NoneType' object has no attribute 'transcribe'" in str(ae):
                            logger.error("[ERROR] Model STT is not available")
                            await self.send(text_data=json.dumps({
                                "type": "error",
                                "message": "Model transkrypcji nie jest dostępny."
                            }))
                        else:
                            raise
                    except Exception as e:
                        logger.error("[ERROR] Error transcription")
                        traceback.print_exc()
                        await self.send(text_data=json.dumps({
                            "type": "error",
                            "message": str(e)
                        }))

    async def finalize_transcription(self):

        logger.info("[FINALIZE] Finalizing transcription")
        self.is_recording = False

        if self.audio_buffer:
            logger.info("[FINALIZE] Processing remaining audio buffer")
            create_wav_from_float32(self.audio_buffer, sample_rate=16000, filename=self.audio_file.name)
            self.audio_buffer.clear()
            audio_path = self.audio_file.name

            try:
                text = transcribe_audio_chunk(audio_path)
                logger.info(f"[FINALIZE] Final transcription chunk: {text}")

                if text.strip():
                    # Dodaje ostatni chunk do pełnej transkrypcji jeśli jeszcze go tam nie ma
                    stripped_text = text.strip()
                    if stripped_text not in self.full_transcription:
                        if self.full_transcription:
                            self.full_transcription += " " + stripped_text
                        else:
                            self.full_transcription = stripped_text
            except Exception as e:
                logger.error(f"[FINALIZE] Error processing final chunk: {e}")

        if self.transcription_task:
            try:
                logger.info("[FINALIZE] Awaiting transcription task")
                await self.transcription_task
            except asyncio.CancelledError:
                logger.error("[FINALIZE] Transcription task cancelled")

        if not self.full_transcription.strip():
            logger.error("[FINALIZE] No transcription to correct")
            return

        def calculate_age_from_pesel(pesel):
            if not pesel or len(pesel) != 11 or not pesel.isdigit():
                return None
                
            try:
                year = int(pesel[0:2])
                month = int(pesel[2:4])
                day = int(pesel[4:6])

                if 1 <= month <= 12:
                    century = 1900
                elif 21 <= month <= 32:
                    century = 2000
                    month -= 20
                else:
                    return None

                birth_date = datetime(century + year, month, day)
                today = datetime.today()
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                return age
            except (ValueError, IndexError):
                return None

        try:
            logger.info(f"[FINALIZE] Running correction on: {self.full_transcription.strip()}")
            corrected_text = await asyncio.get_event_loop().run_in_executor(
                None, correct_full_transcription, self.full_transcription.strip()
            )
            corrected_text = json.loads(corrected_text)
            logger.info(f"[FINALIZE] Corrected transcription: {corrected_text}")
            if 'analyzed_organ' not in corrected_text:
                print("⚠️ Brakuje pola 'analyzed_organ' w JSON-ie!")
                corrected_text['analyzed_organ'] = ''
                
            # Przygotuj dane formularza z priorytetem dla danych z AI
            full_name = corrected_text.get("name", "") + " " + corrected_text.get("surname", "")
            full_name = full_name.strip()
            if not full_name and self.patient_metadata.get("name"):
                full_name = self.patient_metadata.get("name", "")
                
            calculated_age = calculate_age_from_pesel(corrected_text.get("pesel", ""))
            if calculated_age is None and self.patient_metadata.get("age"):
                calculated_age = self.patient_metadata.get("age", "")
                
            # Przygotuj dane do wysłania - priorytet mają dane z AI
            form_data = {
                "organ": corrected_text.get('analyzed_organ', "") or self.patient_metadata.get("organ", ""),
                "name": full_name or self.patient_metadata.get("name", ""),
                "age": str(calculated_age) if calculated_age is not None else self.patient_metadata.get("age", ""),
                "pesel": corrected_text.get("pesel", "") or self.patient_metadata.get("pesel", ""),
                "description": corrected_text.get("description", "")
            }
            logger.info(f"[FINALIZE] Sending form data: {form_data}")
            await self.send(text_data=json.dumps({
                "type": "form_data",
                "formData": form_data,

                "text": corrected_text.get("description", ""),
                "interim": "",
                "is_final": True
            }))
            logger.info("[FINALIZE] Successfully sent form data to frontend")

        except ValueError as ve:
            if "requires `accelerate`" in str(ve):
                logger.error("[FINALIZE] Correction error - missing accelerate package:")
                traceback.print_exc()
                await self.send(text_data=json.dumps({
                    "type": "transcript",
                    "text": self.full_transcription.strip(),
                    "interim": "",
                    "is_final": True,
                    "note": "Używam surowej transkrypcji (błąd modelu korekty)"
                }))
            else:
                raise
        except Exception as e:
            logger.error("[FINALIZE] Error revision:")
            traceback.print_exc()
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": f"Błąd korekty: {str(e)}"
            }))