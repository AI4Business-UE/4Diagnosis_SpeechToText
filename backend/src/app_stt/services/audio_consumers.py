import os
import wave
import enum
import base64
import asyncio
import tempfile
import json
import traceback
import struct
from datetime import datetime

import numpy as np
from channels.generic.websocket import AsyncWebsocketConsumer

from logging_config import logger
from app_stt.services.utils import extract_organs, extract_patient_data
from app_stt.services.data_sanity_check import run_data_sanity_check
from app_stt.services.sanity_logging import append_sanity_record
from app_stt.pipeline import get_pipeline

class RecordingState(enum.Enum):
    IDLE = 'idle'
    RECORDING = 'recording'
    FINALIZING = 'finalizing'

class AudioConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.audio_buffer = []  # Lista Float32Array chunks
        self.audio_recording_task = None
        self.pipeline_task = None
        self.full_transcription = ""  # Przechowuje pełną transkrypcję
        
        self.connection_closed = False 
        self.recording_state = RecordingState.IDLE
        self.patient_metadata = {} # Przechowuje metadane pacjenta
        
        self.chunk_event = asyncio.Event()
        self.audio_swap_lock = asyncio.Lock()
        
        self.wave = None
        self.audio_file = None
        
        self.tmp_dir = os.path.join(os.getcwd(), "app_stt", "data", "tmp_audio")
        os.makedirs(self.tmp_dir, exist_ok=True)
 

    async def _setup(self):
        if self.recording_state == RecordingState.IDLE and (not self.audio_file or self.audio_file.closed):
            self.recording_state = RecordingState.RECORDING
            
            # Readonly IO
            self.audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav", dir=self.tmp_dir)
            # Write interface for received chunks
            self.wave = wave.open(self.audio_file.name, 'wb')
            self.wave.setnchannels(1)
            self.wave.setsampwidth(2)
            self.wave.setframerate(16000)
            
            if not self.audio_recording_task or self.audio_recording_task.done():
                self.audio_recording_task = asyncio.create_task(self.process_buffer())
                
            # Sending ACK message to allow streaming chunks
            await self.send(text_data=json.dumps({
                "type": "recording_start",
                "ack": True
            }))
         

    async def connect(self):
        logger.info("[WS] Client connected")
        await self.accept()
        self.pipeline = get_pipeline()


    async def disconnect(self, close_code):
        logger.error("[WS] WebSocket disconnected")
        self.connection_closed = True
        
        try:
            if self.audio_recording_task:
                self.audio_recording_task.cancel()
                await self.audio_recording_task
        except asyncio.CancelledError:
            logger.warning(f"[DISCONNECT] Cancelled background task during disconnect")
        
        if self.wave is not None:
            self.wave.close()
        if self.audio_file is not None and not self.audio_file.closed:
            self.audio_file.flush()
            self.audio_file.close()


    def _unpack_audio_chunk_from_b64(self, audio_b64): 
        audio_bytes = base64.b64decode(audio_b64)
        
        if len(audio_bytes) % 4:
            raise ValueError("Audio payload is not aligned to Float32 samples")
        
        num_samples = len(audio_bytes) // 4
        audio_chunk = [
            struct.unpack('<f', audio_bytes[i*4:(i+1)*4])[0]
            for i in range(num_samples)
        ]
        
        return audio_chunk
    
    
    def _write_chunks_to_wav(self, float32_chunks, sample_rate=16000, filename=None):
        """
        Create WAV file from list of Float32Array chunks
        """
        # Combine all chunks into one array
        total_samples = sum(len(chunk) for chunk in float32_chunks)
        if total_samples == 0:
            raise ValueError("No audio data to write")

        for chunk in float32_chunks:
            pcm_bytes = np.clip(np.array(chunk), -1.0, 1.0)
            pcm_bytes = (pcm_bytes * 32767).astype("<i2").tobytes() 
            self.wave.writeframesraw(pcm_bytes)
        
        
    async def _flush_remaining_audio(self):
        if self.audio_buffer:
            logger.info("[FINALIZE] Flushing remaining audio buffer")
            async with self.audio_swap_lock:
                chunks = self.audio_buffer
                self.audio_buffer = []
                await asyncio.to_thread(self._write_chunks_to_wav, chunks, 16000, self.audio_file.name)
         
            
    def _calculate_age_from_pesel(self, pesel):
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
        
        
    async def _run_pipeline_and_send(self, audio_path, patient_metadata): 
        try:
            logger.info(f"[FINALIZE] Running pipeline on audio")
            pipeline_results = await asyncio.to_thread(
                self.pipeline.run, audio_path
            )
             
            corrected_text = pipeline_results['corrected_transcript']
            logger.info(f"[FINALIZE] Corrected transcription: {corrected_text}")
            
            patient_data = extract_patient_data(pipeline_results['entities'])
            organs = extract_organs(pipeline_results['entities'])
            full_name = (f"{patient_data['first_name']} {patient_data['last_name']}"
                        if patient_data['first_name'] and patient_data['last_name']
                        else '')
            if not full_name and patient_metadata.get("name"):
                full_name = patient_metadata.get("name", "")
                
            calculated_age = (
                patient_data['age'] or self._calculate_age_from_pesel(patient_data['pesel'])
            )
            if calculated_age is None and patient_metadata.get("age"):
                calculated_age = patient_metadata.get("age", "")
            
            logger.info(f"Dane pacjenta: {patient_data}")
            form_data = {
                "name": full_name or patient_metadata.get("name", ""),
                "organ": organs,
                "age": str(calculated_age) if calculated_age is not None else patient_metadata.get("age", ""),
                "pesel": patient_data['pesel'] or patient_metadata.get("pesel", ""),
                "description": corrected_text
            }

            try:
                sanity_result = run_data_sanity_check(corrected_text, form_data)
                sanity_record = await asyncio.to_thread(append_sanity_record, sanity_result)
                logger.info(
                    "[SANITY_CHECK] status=%s score=%s issues=%s codes=%s",
                    sanity_record["status"],
                    sanity_record["score"],
                    sanity_record["issue_count"],
                    ",".join(sanity_record["issue_codes"]),
                )
            except Exception as sanity_error:
                logger.warning(f"[SANITY_CHECK] Failed to write runtime QA log: {sanity_error}")
             
            logger.info(f"[FINALIZE] Sending form data: {form_data}")
            
            if not self.connection_closed: 
                await self.send(text_data=json.dumps({
                    "type": "form_data",
                    "formData": form_data,
                    "text": corrected_text,
                    "interim": "",
                    "is_final": True
                }))
                logger.info("[FINALIZE] Successfully sent form data to frontend")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("[FINALIZE] Error revision:")
            traceback.print_exc()
            if not self.connection_closed:
                await self.send(text_data=json.dumps({
                    "type": "error",
                    "message": f"Błąd transkrypcji: {str(e)}"
                }))
                
            
    async def receive(self, text_data=None, bytes_data=None):
        try:
            if text_data is None and bytes_data:
                raise ValueError("Raw bytes data not supported. Send JSON.")
            
            msg = json.loads(text_data)

            if "control" in msg and msg["control"] == "stop_recording":
                logger.info("[CTRL] Stop recording")
                await self._finalize_transcription()
                return

            if msg.get("type") in ("metadata", "metadata_update"):
                metadata = msg.get("metadata", {})
                if metadata:
                    self.patient_metadata.update(metadata)
                return

            if msg.get("type") == "recording_start":
                await self._setup()
                metadata = msg.get("metadata", {})
                if metadata:
                    self.patient_metadata.update(metadata)
                logger.info(f"[WS] Recording started...")
                
            if msg.get("type") == "recording_end":
                metadata = msg.get("metadata", {})
                if metadata:
                    self.patient_metadata.update(metadata)
                return

            if (msg.get("type") == "audio_chunk" and msg.get("data") 
                    and self.recording_state == RecordingState.RECORDING):
                metadata = msg.get("metadata", {})
                if metadata:
                    self.patient_metadata.update(metadata)

                audio_data = msg["data"]
                if isinstance(audio_data, dict) and 'data' in audio_data:
                    audio_b64 = audio_data['data']
                elif isinstance(audio_data, str):
                    audio_b64 = audio_data
                else:
                    logger.error(f"[ERROR] Unexpected audio data format: {type(audio_data)}")
                    return
                try:
                    audio_chunk = self._unpack_audio_chunk_from_b64(audio_b64)
                    self.audio_buffer.append(audio_chunk)
                    self.chunk_event.set()
                except Exception as e:
                    logger.error(f"[ERROR] Failed to decode audio chunk: {e}")
                    return
        except Exception as e:
            logger.error(f"[ERROR] Exception in receive: {e}")
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": str(e)
            }))
        

    async def process_buffer(self):
        logger.info("[TRANSCRIBE] Starting buffer processing loop")
        while True:
            await self.chunk_event.wait()
            self.chunk_event.clear()

            if self.recording_state != RecordingState.RECORDING and not self.audio_buffer:
                logger.info("[TRANSCRIBE] Exiting loop (recording stopped and buffer empty)")
                break

            if self.audio_buffer:
                logger.info("[TRANSCRIBE] Processing audio buffer")
                async with self.audio_swap_lock:
                    chunks = self.audio_buffer
                    self.audio_buffer = []

                    await asyncio.to_thread(self._write_chunks_to_wav, chunks, 16000, self.audio_file.name)
                logger.info(f"[AUDIO] Written new chunks to WAV file (Total chunks: {len(chunks)})") 
                

    async def _finalize_transcription(self):
        if self.recording_state != RecordingState.RECORDING:
            return
        
        logger.info("[FINALIZE] Finalizing transcription")
        self.recording_state = RecordingState.FINALIZING
        
        try:
            await self._flush_remaining_audio()
            
            # Setting event here to allow the task
            # to break the loop and exit cleanly
            self.chunk_event.set()
            if self.audio_recording_task:
                await self.audio_recording_task
                self.audio_recording_task = None
            
            self.wave.close()
            self.audio_file.close()
            
            
            await self._run_pipeline_and_send(
                self.audio_file.name, self.patient_metadata.copy()
            )
            
        except asyncio.CancelledError:
            raise
        finally:
            self.recording_state = RecordingState.IDLE
