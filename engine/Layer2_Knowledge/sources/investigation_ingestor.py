"""
Investigation document ingestor.

Compatibility bridge so investigation controller uses assimilation namespace.
"""

from engine.Layer2_Knowledge.knowledge_ingestor import IngestionSummary, ingest_documents

__all__ = ["IngestionSummary", "ingest_documents"]
