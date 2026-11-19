"""Publiczne reeksporty pakietu pipeline.

Importy są leniwe (PEP 562), żeby modułowe ścieżki takie jak
``app_stt.pipeline.utils.llm.gateway`` dało się zaimportować bez wciągania
całej aplikacji (potrzebne m.in. offline'owym testom narzędzia eval).
"""

from __future__ import annotations

__all__ = ["Pipeline", "PipelineConfig", "get_pipeline"]

_EXPORTS = {
    "Pipeline": ".pipeline",
    "get_pipeline": ".pipeline",
    "PipelineConfig": ".config",
}


def __getattr__(name):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(_EXPORTS))
