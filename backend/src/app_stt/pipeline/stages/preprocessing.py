from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ..config import PipelineConfig


class AudioPreprocessor:
    """
    Converts raw audio to a 16 kHz mono WAV ready for STT.

    Optional steps (controlled via PipelineConfig):
      - peak volume normalization
      - bandpass filter (200–7900 Hz)
      - noise reduction (spectral gating via noisereduce)
      - VAD — Voice Activity Detection via Silero VAD (strips silence)

    Each step is guarded by a try/except so missing optional dependencies
    (noisereduce, silero VAD) don't crash the pipeline unless the feature
    is actually enabled.
    """

    def __init__(self, config: PipelineConfig):
        self.cfg = config
        self._vad_model = None
        self._vad_utils = None
        output_dir = Path(config.preprocessing_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = output_dir

    # ── public ───────────────────────────────────────────────────────────────

    def process(self, input_path: str | Path) -> dict:
        """
        Preprocess audio file and write result to output_dir.

        Returns a metadata dict including 'output_path' used by the STT stage.
        """
        import librosa
        import soundfile as sf

        input_path = Path(input_path)
        output_path = self._build_output_path(input_path)

        audio, _ = librosa.load(input_path, sr=self.cfg.target_sr, mono=True)
        original_duration = len(audio) / self.cfg.target_sr

        volume_meta: dict = {}
        if self.cfg.use_volume_normalization:
            audio, volume_meta = self._normalize_peak(audio)
        else:
            volume_meta = {
                "volume_normalization_enabled": False,
                "volume_target_peak": None,
                "volume_original_peak": None,
                "volume_gain_applied": None,
            }

        bandpass_enabled = False
        if self.cfg.use_bandpass_filter:
            audio = self._apply_bandpass(audio, self.cfg.target_sr)
            bandpass_enabled = True

        noise_meta: dict = {}
        if self.cfg.use_noise_reduction:
            audio, noise_meta = self._apply_noise_reduction(audio, self.cfg.target_sr)
        else:
            noise_meta = {
                "noise_reduction_enabled": False,
                "noise_reduction_method": None,
                "noise_reduction_stationary": None,
                "noise_reduction_prop_decrease": None,
            }

        vad_meta: dict = {}
        if self.cfg.use_vad:
            audio, vad_meta = self._apply_vad(audio, self.cfg.target_sr)
        else:
            vad_meta = {
                "vad_enabled": False,
                "vad_speech_segments": None,
                "vad_removed_silence": False,
                "vad_threshold": None,
            }

        sf.write(output_path, np.asarray(audio, dtype=np.float32), self.cfg.target_sr, subtype="PCM_16")

        return {
            "input_path": str(input_path),
            "output_path": str(output_path),
            "target_sample_rate": self.cfg.target_sr,
            "mono": True,
            "bandpass_enabled": bandpass_enabled,
            "high_pass_hz": self.cfg.high_pass_hz if bandpass_enabled else None,
            "low_pass_hz": self.cfg.low_pass_hz if bandpass_enabled else None,
            "original_duration_seconds": round(original_duration, 2),
            "output_duration_seconds": round(len(audio) / self.cfg.target_sr, 2),
            **volume_meta,
            **noise_meta,
            **vad_meta,
            "status": "ok",
            "error": None,
        }

    # ── private helpers ───────────────────────────────────────────────────────

    def _build_output_path(self, input_path: Path) -> Path:
        suffixes = []
        if self.cfg.use_volume_normalization:
            suffixes.append("norm")
        if self.cfg.use_bandpass_filter:
            suffixes.append("bandpass")
        if self.cfg.use_noise_reduction:
            suffixes.append("denoise")
        if self.cfg.use_vad:
            suffixes.append("vad")
        suffix_str = "_" + "_".join(suffixes) if suffixes else ""
        name = f"{input_path.stem}_16khz_mono{suffix_str}.wav"
        return self.output_dir / name

    def _normalize_peak(self, audio: np.ndarray) -> tuple[np.ndarray, dict]:
        peak = np.max(np.abs(audio))
        if peak == 0:
            return audio, {
                "volume_normalization_enabled": True,
                "volume_target_peak": self.cfg.volume_target_peak,
                "volume_original_peak": 0.0,
                "volume_gain_applied": 1.0,
            }
        gain = self.cfg.volume_target_peak / peak
        return audio * gain, {
            "volume_normalization_enabled": True,
            "volume_target_peak": self.cfg.volume_target_peak,
            "volume_original_peak": round(float(peak), 6),
            "volume_gain_applied": round(float(gain), 3),
        }

    def _apply_bandpass(self, audio: np.ndarray, sr: int) -> np.ndarray:
        from scipy.signal import butter, sosfiltfilt

        nyquist = sr / 2
        high_cut = min(self.cfg.low_pass_hz, nyquist - 1)
        sos = butter(
            self.cfg.filter_order,
            [self.cfg.high_pass_hz, high_cut],
            btype="bandpass",
            fs=sr,
            output="sos",
        )
        return sosfiltfilt(sos, audio)

    def _apply_noise_reduction(self, audio: np.ndarray, sr: int) -> tuple[np.ndarray, dict]:
        import noisereduce as nr

        denoised = nr.reduce_noise(
            y=audio,
            sr=sr,
            stationary=self.cfg.noise_reduction_stationary,
            prop_decrease=self.cfg.noise_reduction_prop_decrease,
        )
        return denoised, {
            "noise_reduction_enabled": True,
            "noise_reduction_method": "spectral_gating",
            "noise_reduction_stationary": self.cfg.noise_reduction_stationary,
            "noise_reduction_prop_decrease": self.cfg.noise_reduction_prop_decrease,
        }

    def _apply_vad(self, audio: np.ndarray, sr: int) -> tuple[np.ndarray, dict]:
        import torch

        model, get_ts, collect = self._load_silero_vad()
        audio_tensor = torch.tensor(audio, dtype=torch.float32)

        speech_timestamps = get_ts(
            audio_tensor,
            model,
            sampling_rate=sr,
            threshold=self.cfg.vad_threshold,
            min_speech_duration_ms=self.cfg.vad_min_speech_duration_ms,
            min_silence_duration_ms=self.cfg.vad_min_silence_duration_ms,
            speech_pad_ms=self.cfg.vad_speech_pad_ms,
        )

        if not speech_timestamps:
            return audio, {
                "vad_enabled": True,
                "vad_speech_segments": 0,
                "vad_removed_silence": False,
                "vad_threshold": self.cfg.vad_threshold,
            }

        speech_audio = collect(speech_timestamps, audio_tensor).numpy()
        return speech_audio, {
            "vad_enabled": True,
            "vad_speech_segments": len(speech_timestamps),
            "vad_removed_silence": True,
            "vad_threshold": self.cfg.vad_threshold,
        }

    def _load_silero_vad(self):
        import torch

        if self._vad_model is not None:
            return self._vad_model, *self._vad_utils

        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
        )
        get_speech_timestamps, _, _, _, collect_chunks = utils
        self._vad_model = model
        self._vad_utils = (get_speech_timestamps, collect_chunks)
        return model, get_speech_timestamps, collect_chunks
