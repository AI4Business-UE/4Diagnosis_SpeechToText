import enum
import sys
import types
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from eval_tool import runtime


def _install_runtime_dependencies(monkeypatch, events, guard_error=None, host=None):
    django = types.ModuleType("django")
    django.setup = lambda: events.append("django.setup")
    monkeypatch.setitem(sys.modules, "django", django)

    package_names = (
        "app_stt",
        "app_stt.pipeline",
        "app_stt.pipeline.stages",
        "app_stt.pipeline.stages.rag",
        "app_stt.pipeline.utils",
        "app_stt.pipeline.utils.llm",
    )
    for name in package_names:
        package = types.ModuleType(name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, name, package)

    host = {"configured": True, "host": "openrouter"} if host is None else host
    llm_client = types.ModuleType("app_stt.pipeline.utils.llm.client")
    llm_client.is_configured = lambda: host["configured"]
    llm_client.active_host = lambda: host["host"]
    monkeypatch.setitem(sys.modules, llm_client.__name__, llm_client)

    config_module = types.ModuleType("app_stt.pipeline.config")

    class ClientMode(enum.Enum):
        IN_MEMORY = "in_memory"

    @dataclass
    class PipelineConfig:
        qdrant_client_mode: ClientMode
        stt_model: str = "whisper_local"
        transcription_model: str = "openai/gpt-transcribe"
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


def _args(**overrides):
    values = {"stt_model": None, "whisper_model": None, "ner_strategy": None}
    values.update(overrides)
    return SimpleNamespace(**values)


def test_runtime_defers_qdrant_indexing_until_pipeline_factory(monkeypatch):
    events = []
    _install_runtime_dependencies(monkeypatch, events)

    prepared = runtime.prepare_runtime(_args())

    assert events == ["django.setup"]
    prepared.pipeline_factory()
    assert events == ["django.setup", "guard", "index", "pipeline"]


def test_runtime_does_not_index_or_construct_pipeline_with_cached_qdrant(monkeypatch):
    events = []
    _install_runtime_dependencies(monkeypatch, events, ValueError("cached client"))

    prepared = runtime.prepare_runtime(_args())

    with pytest.raises(ValueError, match="cached client"):
        prepared.pipeline_factory()

    assert events == ["django.setup", "guard"]


def test_runtime_raises_polish_error_when_active_host_is_not_configured(monkeypatch):
    events = []
    host = {"configured": False, "host": "openai"}
    _install_runtime_dependencies(monkeypatch, events, host=host)

    with pytest.raises(ValueError, match="Host LLM nie jest skonfigurowany"):
        runtime.prepare_runtime(_args())


def test_runtime_records_explicit_host_instead_of_inferred_provider(monkeypatch):
    events = []
    host = {"configured": True, "host": "openai"}
    _install_runtime_dependencies(monkeypatch, events, host=host)

    prepared = runtime.prepare_runtime(_args())

    assert prepared.resolved_config["llm_host"] == "openai"
    assert "llm_api_provider" not in prepared.resolved_config


@pytest.mark.parametrize(
    ("stt_model", "expected_model_id"),
    [
        ("gpt-transcribe", "openai/gpt-transcribe"),
        ("whisper_hosted", "openai/gpt-transcribe"),
        ("whisper_local", "openai/whisper-base"),
    ],
)
def test_runtime_records_stt_model_id_from_config(monkeypatch, stt_model, expected_model_id):
    events = []
    _install_runtime_dependencies(monkeypatch, events)

    prepared = runtime.prepare_runtime(_args(stt_model=stt_model))

    assert prepared.resolved_config["stt_model_id"] == expected_model_id
