import importlib.util
from pathlib import Path

import pytest


def _load_qdrant_client_module():
    client_path = (
        Path(__file__).resolve().parents[4]
        / "src"
        / "app_stt"
        / "pipeline"
        / "stages"
        / "rag"
        / "qdrant"
        / "client.py"
    )
    spec = importlib.util.spec_from_file_location("qdrant_client_under_test", client_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_qdrant_fresh_process_guard_rejects_a_cached_client(monkeypatch):
    client = _load_qdrant_client_module()
    monkeypatch.setattr(client, "_client", object())

    with pytest.raises(ValueError, match="nowym procesie"):
        client.ensure_qdrant_client_uninitialized()
