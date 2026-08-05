__all__ = ["QdrantClient", "QdrantClientMode", "QdrantRetriever", "build_queries", "index_database"]


def __getattr__(name):
    if name in {"QdrantClient", "QdrantClientMode"}:
        from .client import QdrantClient, QdrantClientMode

        return {"QdrantClient": QdrantClient, "QdrantClientMode": QdrantClientMode}[name]
    if name == "build_queries":
        from .queries import build_queries

        return build_queries
    if name == "index_database":
        from .indexing import index_database

        return index_database
    if name == "QdrantRetriever":
        from .retriever import QdrantRetriever

        return QdrantRetriever
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
