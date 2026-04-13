"""
Vector Store — Per-Space ChromaDB Collections
===============================================
Extended to support separate collections per knowledge space
(legal, event, economic, strategic).

ChromaDB handles embedding internally using its default model
(all-MiniLM-L6-v2). No external embedding service needed.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings
    _HAS_CHROMADB = True
except ImportError:
    _HAS_CHROMADB = False
    logger.warning("chromadb not installed — vector search unavailable")


# Knowledge space → collection name mapping
_SPACE_COLLECTIONS = {
    "legal":     "diplomatic_legal",
    "event":     "diplomatic_event",
    "economic":  "diplomatic_economic",
    "strategic": "diplomatic_strategic",
}


class VectorStore:
    """
    Multi-collection vector store backed by ChromaDB.

    Each knowledge space gets its own collection for isolated,
    high-precision retrieval:
        - legal     → treaties, laws, agreements (exact matching)
        - event     → news, statements (recency-weighted)
        - economic  → trade data, sanctions (numerical context)
        - strategic → analysis, think-tank reports (nuanced)
    """

    def __init__(self, data_dir: str = None):
        self.available = _HAS_CHROMADB
        self.collections: Dict[str, Any] = {}

        if not _HAS_CHROMADB:
            logger.warning("VectorStore: chromadb not available — all operations are no-ops")
            return

        if data_dir is None:
            data_dir = os.getenv("CHROMA_PATH", "./data/chroma")

        persist_dir = Path(data_dir).resolve()
        persist_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.client = chromadb.PersistentClient(path=str(persist_dir))
        except Exception:
            settings = Settings(is_persistent=True, persist_directory=str(persist_dir))
            self.client = chromadb.Client(settings)

        # Initialize all space collections
        for space, col_name in _SPACE_COLLECTIONS.items():
            self.collections[space] = self.client.get_or_create_collection(
                name=col_name,
                metadata={"hnsw:space": "cosine"},
            )

        logger.info(
            "VectorStore initialized with %d collections at %s",
            len(self.collections), persist_dir,
        )

    # ── Add documents ────────────────────────────────────────────

    def add_chunks(self, space: str, chunks: List[Dict[str, Any]]) -> int:
        """
        Add chunks to a specific knowledge space collection.

        Args:
            space:   Knowledge space (legal, event, economic, strategic).
            chunks:  List of chunk dicts (must have 'id', 'text', 'metadata').

        Returns:
            Number of chunks added.
        """
        if not self.available:
            return 0

        collection = self.collections.get(space)
        if collection is None:
            logger.warning("Unknown knowledge space: %s — skipping", space)
            return 0

        if not chunks:
            return 0

        ids = [c["id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = []
        for c in chunks:
            # ChromaDB metadata must be flat (str, int, float, bool)
            meta = {}
            raw_meta = c.get("metadata", {})
            for k, v in raw_meta.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v
                elif isinstance(v, list):
                    meta[k] = ", ".join(str(x) for x in v)
                elif v is not None:
                    meta[k] = str(v)
            metadatas.append(meta)

        try:
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
            logger.info("Added %d chunks to '%s' collection", len(chunks), space)
            return len(chunks)
        except Exception as exc:
            logger.error("Failed to add chunks to '%s': %s", space, exc)
            return 0

    # ── Legacy single-collection interface ───────────────────────

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ):
        """Legacy interface — adds to 'event' collection by default."""
        if not self.available:
            return
        collection = self.collections.get("event")
        if collection:
            collection.upsert(documents=documents, metadatas=metadatas, ids=ids)

    # ── Search ───────────────────────────────────────────────────

    def search(
        self,
        query: str,
        space: Optional[str] = None,
        top_k: int = 10,
        where: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search across one or all knowledge spaces.

        Args:
            query:  Search query text.
            space:  Optional space to search (None = search all).
            top_k:  Number of results per space.
            where:  Optional ChromaDB where filter dict.

        Returns:
            List of result dicts with: id, content, metadata, score, space.
        """
        if not self.available:
            return []

        spaces_to_search = (
            [space] if space and space in self.collections
            else list(self.collections.keys())
        )

        all_results = []
        for sp in spaces_to_search:
            collection = self.collections[sp]

            try:
                query_params = {
                    "query_texts": [query],
                    "n_results": min(top_k, collection.count() or top_k),
                }
                if where:
                    query_params["where"] = where

                results = collection.query(**query_params)

                if results["documents"] and results["documents"][0]:
                    for i in range(len(results["documents"][0])):
                        all_results.append({
                            "id":       results["ids"][0][i],
                            "content":  results["documents"][0][i],
                            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                            "score":    results["distances"][0][i] if results["distances"] else 0.0,
                            "space":    sp,
                        })
            except Exception as exc:
                logger.warning("Search failed in '%s': %s", sp, exc)

        # Sort by score (lower distance = better for cosine)
        all_results.sort(key=lambda x: x["score"])
        return all_results[:top_k]

    # ── Stats ────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, int]:
        """Get document counts per collection."""
        if not self.available:
            return {"status": "unavailable"}

        stats = {}
        for space, collection in self.collections.items():
            try:
                stats[space] = collection.count()
            except Exception:
                stats[space] = -1
        stats["total"] = sum(v for v in stats.values() if v > 0)
        return stats

    def clear_space(self, space: str) -> bool:
        """Clear all documents from a knowledge space."""
        if not self.available:
            return False
        collection = self.collections.get(space)
        if collection is None:
            return False
        try:
            # Delete collection and recreate
            self.client.delete_collection(_SPACE_COLLECTIONS[space])
            self.collections[space] = self.client.get_or_create_collection(
                name=_SPACE_COLLECTIONS[space],
                metadata={"hnsw:space": "cosine"},
            )
            return True
        except Exception as exc:
            logger.error("Failed to clear '%s': %s", space, exc)
            return False


# ── Module-level instance ────────────────────────────────────────

# Lazy instantiation to avoid import-time side effects
_store = None

def get_vector_store(data_dir: str = None) -> VectorStore:
    """Get or create the singleton VectorStore instance."""
    global _store
    if _store is None:
        _store = VectorStore(data_dir)
    return _store


__all__ = ["VectorStore", "get_vector_store"]
