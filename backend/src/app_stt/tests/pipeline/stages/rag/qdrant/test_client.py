import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest


def _load_qdrant_client_module():
    client_path = (
        Path(__file__).resolve().parents[5]
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


class TestQdrantClientTests(unittest.TestCase):
    def test_fresh_process_guard_rejects_a_cached_client(self):
        client = _load_qdrant_client_module()

        with patch.object(client, "_client", object()), pytest.raises(
            ValueError, match="nowym procesie"
        ):
            client.ensure_qdrant_client_uninitialized()
