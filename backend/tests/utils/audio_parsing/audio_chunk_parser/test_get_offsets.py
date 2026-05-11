
import pytest
from src.utils.audio_parsing.audio_chunk_parser import AudioChunkParser


def test_get_offsets_empty_initial():
    parser = AudioChunkParser()
    assert parser.get_offsets() == [], "Should return empty list when no offsets loaded."


def test_get_offsets_after_loading_valid_offsets():
    parser = AudioChunkParser()
    input_offsets = [(0, 1000), (1, 2500), (2, 4000)]
    parser.load_offsets(input_offsets)
    assert parser.get_offsets() == input_offsets, "Should return the same offsets as loaded."


def test_get_offsets_replaces_previous_offsets():
    parser = AudioChunkParser()
    parser.load_offsets([(0, 100)])
    parser.load_offsets([(1, 200), (2, 300)])
    assert parser.get_offsets() == [(1, 200), (2, 300)], "Should reflect only the latest loaded offsets."


def test_get_offsets_with_non_integer_offsets():
    parser = AudioChunkParser()
    with pytest.raises(TypeError):
        parser.load_offsets([(0, "1000")])  # Improper format


def test_get_offsets_with_negative_values():
    parser = AudioChunkParser()
    offsets = [(0, -100), (1, 200)]
    parser.load_offsets(offsets)
    assert parser.get_offsets() == offsets, "Should accept negative offsets if not explicitly disallowed."


def test_get_offsets_with_unsorted_offsets():
    parser = AudioChunkParser()
    unsorted_offsets = [(2, 3000), (0, 1000), (1, 2000)]
    parser.load_offsets(unsorted_offsets)
    assert parser.get_offsets() == unsorted_offsets, "Should preserve order unless sorting is required."

