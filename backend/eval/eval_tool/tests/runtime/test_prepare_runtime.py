import enum
import sys
import types
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from eval_tool import runtime


def _install_runtime_dependencies(monkeypatch, events, guard_error=None):
    django = types.ModuleType("django")
    django.setup = lambda: events.append("django.setup")
    monkeypatch.setitem(sys.modules, "django", django)

    package_names = (
        "app_stt",
        "app_stt.pipeline",
        "app_stt.pipeline.stages",
        "app_stt.pipeline.stages.rag",
    )
    for name in package_names:
        package = types.ModuleType(name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, name, package)

    config_module = types.ModuleType("app_stt.pipeline.config")

    class ClientMode(enum.Enum):
        IN_MEMORY = "in_memory"

    @dataclass
    class PipelineConfig:
        qdrant_client_mode: ClientMode
        stt_model: str = "whisper_local"
        whisper_model: str = "base"
        ner_strategy: str = "chained"

        @property
        def whisper_hf_id(self):
            return "openai/whisper-base"

    config_module.PipelineConfig = PipelineConfig
    monkeypatch.setitem(sys.modules, config_module.__name__, config_module)

    pipeline_module = types.ModuleType("app_stt.pipeline.pipeline")

    class Pipeline:
        def __init__(self, _config):
            events.append("pipeline")

    pipeline_module.Pipeline = Pipeline
    monkeypatch.setitem(sys.modules, pipeline_module.__name__, pipeline_module)

    qdrant_module = types.ModuleType("app_stt.pipeline.stages.rag.qdrant")
    qdrant_module.QdrantClientMode = ClientMode

    def ensure_uninitialized():
        events.append("guard")
        if guard_error is not None:
            raise guard_error

    qdrant_module.ensure_qdrant_client_uninitialized = ensure_uninitialized
    qdrant_module.index_database = lambda _config: events.append("index")
    monkeypatch.setitem(sys.modules, qdrant_module.__name__, qdrant_module)


def _args():
    return SimpleNamespace(stt_model=None, whisper_model=None, ner_strategy=None)


def test_runtime_defers_qdrant_indexing_until_pipeline_factory(monkeypatch):
    events = []
    _install_runtime_dependencies(monkeypatch, events)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    prepared = runtime.prepare_runtime(_args())

    assert events == ["django.setup"]
    prepared.pipeline_factory()
    assert events == ["django.setup", "guard", "index", "pipeline"]


def test_runtime_does_not_index_or_construct_pipeline_with_cached_qdrant(monkeypatch):
    events = []
    _install_runtime_dependencies(monkeypatch, events, ValueError("cached client"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    prepared = runtime.prepare_runtime(_args())

    with pytest.raises(ValueError, match="cached client"):
        prepared.pipeline_factory()

    assert events == ["django.setup", "guard"]
