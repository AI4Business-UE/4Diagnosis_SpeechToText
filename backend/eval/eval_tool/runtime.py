from __future__ import annotations

import dataclasses
import enum
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

BACKEND_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class EvaluationRuntime:
    pipeline_factory: Callable[[], Any]
    resolved_config: dict[str, Any]


def prepare_runtime(args: Any) -> EvaluationRuntime:
    """Bootstrap Django and defer isolated RAG indexing until evaluation starts."""
    source_dir = BACKEND_DIR / "src"
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stt.settings")
    # Prevent AppSttConfig.ready() from constructing the web application's singleton
    # pipeline while still allowing the STT stage to read the Keyword model.
    os.environ["TESTING"] = "1"
    import django

    django.setup()

    from app_stt.pipeline.config import PipelineConfig
    from app_stt.pipeline.pipeline import Pipeline
    from app_stt.pipeline.stages.rag.qdrant import (
        QdrantClientMode, ensure_qdrant_client_uninitialized, index_database)

    config_values: dict[str, Any] = {"qdrant_client_mode": QdrantClientMode.IN_MEMORY}
    for argument, field in (
        ("stt_model", "stt_model"),
        ("whisper_model", "whisper_model"),
        ("ner_strategy", "ner_strategy"),
    ):
        value = getattr(args, argument, None)
        if value is not None:
            config_values[field] = value
    config = PipelineConfig(**config_values)
    try:
        whisper_hf_id = config.whisper_hf_id
    except KeyError as error:
        raise ValueError(f"Nieznany model Whisper: {config.whisper_model}") from error

    if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")):
        raise ValueError("Brak klucza OPENROUTER_API_KEY lub OPENAI_API_KEY.")

    resolved_config = {
        field.name: _json_config_value(getattr(config, field.name))
        for field in dataclasses.fields(config)
    }
    resolved_config["whisper_hf_id"] = whisper_hf_id
    resolved_config["stt_model_id"] = (
        "openai/gpt-transcribe" if config.stt_model == "gpt-transcribe" else whisper_hf_id
    )
    resolved_config["llm_api_provider"] = "openrouter" if os.getenv("OPENROUTER_API_KEY") else "openai"

    def pipeline_factory() -> Any:
        ensure_qdrant_client_uninitialized()
        index_database(config)
        return Pipeline(config)

    return EvaluationRuntime(
        pipeline_factory=pipeline_factory,
        resolved_config=resolved_config,
    )


def _json_config_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "name"):
        return value.name
    return str(value)
