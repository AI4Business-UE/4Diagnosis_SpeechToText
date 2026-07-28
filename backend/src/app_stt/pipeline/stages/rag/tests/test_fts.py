import pytest

from .. import fts

@pytest.fixture
def text_to_lemmatize():
    return "Kot siedzi na stole"

@pytest.fixture
def patched_analysis(monkeypatch):
    def mock_return(_):
        return [
            (0, 1, ("Kot", "Kot", "cokolwiek", [], [])),
            (0, 1, ("Kot", "Kota", "cokolwiek", [], [])),
            (1, 2, ("siedzi", "siedzieć", "cokolwiek", [], [])),
            (2, 3, ("na", "na", "cokolwiek", [], [])),
            (3, 4, ("qwerty", "qwerty", "ign", [], [])),
            (3, 4, ("stole", "stół", "cokolwiek", [], [])),
            (4, 5, ("placeholder", "placeholder", "cokolwiek", [], ["daw."]))
        ]
    
    monkeypatch.setattr(fts, "perform_morphological_analysis", mock_return)
    
def test_fts_mocked(patched_analysis, text_to_lemmatize):
    text = fts.prepare_fts_text(text_to_lemmatize)
    assert "kot siedzieć na stół" == text 