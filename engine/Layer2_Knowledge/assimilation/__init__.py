"""Knowledge assimilation package — evidence extraction and ingestion."""

# Lazy imports: the legacy investigation_ingestor pulls in sqlalchemy/db
# which may not be available in all environments.  Defer until accessed.

from engine.Layer2_Knowledge.assimilation.evidence_assimilator import (  # noqa: F401
    extract_observations,
    extract_observations_batch,
    extract_signals,
    extract_signals_batch,
)

__all__ = [
    "extract_observations",
    "extract_observations_batch",
    "extract_signals",
    "extract_signals_batch",
    "IngestionSummary",
    "ingest_documents",
]


def __getattr__(name: str):
    """Lazy-load legacy ingestion symbols only when requested."""
    if name in ("IngestionSummary", "ingest_documents"):
        from importlib import import_module
        _impl = import_module("engine.Layer2_Knowledge.sources.investigation_ingestor")
        val = getattr(_impl, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
