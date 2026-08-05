__all__ = ["Pipeline", "PipelineConfig", "get_pipeline"]


def __getattr__(name):
    if name == "PipelineConfig":
        from .config import PipelineConfig

        return PipelineConfig
    if name in {"Pipeline", "get_pipeline"}:
        from .pipeline import Pipeline, get_pipeline

        return {"Pipeline": Pipeline, "get_pipeline": get_pipeline}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
