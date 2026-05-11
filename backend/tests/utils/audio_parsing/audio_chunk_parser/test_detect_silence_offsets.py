
import pytest
from pydub import AudioSegment
from pydub.generators import Sine
from src.utils.audio_parsing.audio_chunk_parser import AudioChunkParser

def generate_audio_with_silence():
    sine_wave = Sine(440).to_audio_segment(duration=1000)  # 1s tone
    silence = AudioSegment.silent(duration=1000)           # 1s silence
    return sine_wave + silence + sine_wave

def test_detect_silence_offsets_finds_one_silence():
    parser = AudioChunkParser()
    wave = generate_audio_with_silence()
    silences = parser.detect_silence_offsets(wave)

    assert isinstance(silences, list)
    assert len(silences) >= 1
    for s in silences:
        assert isinstance(s, tuple)
        assert len(s) == 2
        assert s[1] > s[0]

def test_detect_silence_offsets_on_loud_audio():
    parser = AudioChunkParser()
    wave = Sine(440).to_audio_segment(duration=3000)  # 3s tone, no silence
    silences = parser.detect_silence_offsets(wave)

    assert isinstance(silences, list)
    assert len(silences) == 0

def test_detect_silence_offsets_on_all_silence():
    parser = AudioChunkParser()
    wave = AudioSegment.silent(duration=2000)  # Entire clip is silence
    silences = parser.detect_silence_offsets(wave)

    assert len(silences) == 1  # One big silence region
    assert silences[0][1] > silences[0][0]
