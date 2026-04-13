"""
Knowledge Indexer — Ingest → Chunk → Embed → Store
=====================================================
Watches the normalized document archive and indexes new documents
into the multi-index knowledge system.

This is the bridge between Layer 1 (collection) and Layer 2 (knowledge).
"""

import os
import json
import logging
import glob
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

from engine.Layer2_Knowledge.chunker import intelligent_chunker
from .vector_store import get_vector_store
from engine.Layer2_Knowledge.document_classifier import document_classifier


class KnowledgeIndexer:
    """
    Index normalized documents into the multi-index knowledge system.

    Pipeline:
        1. Load normalized document JSON
        2. Classify document type
        3. Chunk intelligently (preserving structure)
        4. Embed & store in correct knowledge space collection
        5. Record indexing metadata
    """

    def __init__(
        self,
        normalized_dir: str = None,
        data_dir: str = None,
        index_record_path: str = None,
    ):
        if normalized_dir is None:
            normalized_dir = os.path.join("data", "archive", "normalized")
        if data_dir is None:
            data_dir = os.path.join("data", "chroma")
        if index_record_path is None:
            index_record_path = os.path.join("data", "archive", "records", "indexed.json")

        self.normalized_dir = normalized_dir
        self.vector_store = get_vector_store(data_dir)
        self.index_record_path = index_record_path

        # Track which documents have been indexed
        self._indexed_ids = self._load_index_record()

    # ── Public API ───────────────────────────────────────────────

    def index_document(self, doc_path: str) -> Dict[str, Any]:
        """
        Index a single normalized document.

        Args:
            doc_path: Path to normalized document JSON file.

        Returns:
            Dict with: doc_id, chunks_created, space, status.
        """
        try:
            with open(doc_path, "r", encoding="utf-8") as f:
                doc = json.load(f)
        except Exception as exc:
            logger.error("Failed to read %s: %s", doc_path, exc)
            return {"status": "error", "error": str(exc)}

        doc_id = doc.get("id", "unknown")

        # Skip if already indexed
        if doc_id in self._indexed_ids:
            return {"doc_id": doc_id, "status": "already_indexed"}

        # Classify if not already classified
        metadata = doc.get("metadata", {})
        if not metadata.get("document_type") or metadata["document_type"] == "unknown":
            classification = document_classifier.classify({
                "content": doc.get("text", ""),
                "metadata": metadata,
            })
            metadata["document_type"] = classification.document_type.value
            metadata["knowledge_space"] = (
                "legal" if document_classifier.is_foundational({"content": doc.get("text", ""), "metadata": metadata})
                else metadata.get("knowledge_space", "event")
            )
            doc["metadata"] = metadata

        # Determine knowledge space
        space = metadata.get("knowledge_space", "event")
        if space not in ("legal", "event", "economic", "strategic"):
            space = "event"  # Default fallback

        # Chunk
        chunks = intelligent_chunker.chunk(doc)

        if not chunks:
            logger.warning("No chunks produced for doc %s", doc_id)
            return {"doc_id": doc_id, "chunks_created": 0, "space": space, "status": "empty"}

        # Store in vector DB
        added = self.vector_store.add_chunks(space, chunks)

        # Record indexing
        self._indexed_ids[doc_id] = {
            "path":           doc_path,
            "space":          space,
            "chunks_created": added,
            "indexed_at":     datetime.utcnow().isoformat() + "Z",
        }
        self._save_index_record()

        logger.info(
            "Indexed doc %s → %d chunks in '%s' space",
            doc_id, added, space,
        )

        return {
            "doc_id":         doc_id,
            "chunks_created": added,
            "space":          space,
            "status":         "indexed",
        }

    def index_directory(self, dir_path: str = None) -> Dict[str, Any]:
        """
        Batch-index all unindexed documents in a directory.

        Args:
            dir_path: Path to directory with normalized JSON files.
                      Defaults to self.normalized_dir.

        Returns:
            Dict with: total_found, indexed, skipped, errors.
        """
        if dir_path is None:
            dir_path = self.normalized_dir

        # Find all JSON files recursively
        pattern = os.path.join(dir_path, "**", "*.json")
        json_files = glob.glob(pattern, recursive=True)

        stats = {"total_found": len(json_files), "indexed": 0, "skipped": 0, "errors": 0}

        for filepath in json_files:
            result = self.index_document(filepath)
            status = result.get("status", "error")

            if status == "indexed":
                stats["indexed"] += 1
            elif status == "already_indexed":
                stats["skipped"] += 1
            else:
                stats["errors"] += 1

        logger.info(
            "Batch index: %d found, %d indexed, %d skipped, %d errors",
            stats["total_found"], stats["indexed"],
            stats["skipped"], stats["errors"],
        )

        return stats

    def reindex_all(self) -> Dict[str, Any]:
        """
        Full reindex — clears all collections and rebuilds.

        WARNING: This is destructive. Use only for schema changes.
        """
        logger.warning("Starting full reindex — clearing all collections")

        # Clear all spaces
        for space in ("legal", "event", "economic", "strategic"):
            self.vector_store.clear_space(space)

        # Reset index record
        self._indexed_ids = {}
        self._save_index_record()

        # Re-index everything
        return self.index_directory()

    def get_stats(self) -> Dict[str, Any]:
        """Get indexing statistics."""
        return {
            "indexed_documents": len(self._indexed_ids),
            "vector_store": self.vector_store.get_stats(),
        }

    # ── Index record persistence ─────────────────────────────────

    def _load_index_record(self) -> Dict[str, Dict]:
        """Load the record of indexed document IDs."""
        if os.path.exists(self.index_record_path):
            try:
                with open(self.index_record_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_index_record(self):
        """Persist the index record."""
        os.makedirs(os.path.dirname(self.index_record_path), exist_ok=True)
        with open(self.index_record_path, "w", encoding="utf-8") as f:
            json.dump(self._indexed_ids, f, ensure_ascii=False, indent=2)


# ── Module-level convenience ─────────────────────────────────────

_indexer = None

def get_knowledge_indexer(**kwargs) -> KnowledgeIndexer:
    """Get or create the singleton KnowledgeIndexer instance."""
    global _indexer
    if _indexer is None:
        _indexer = KnowledgeIndexer(**kwargs)
    return _indexer


__all__ = ["KnowledgeIndexer", "get_knowledge_indexer"]
