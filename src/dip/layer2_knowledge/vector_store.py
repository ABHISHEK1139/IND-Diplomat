"""
ChromaDB Vector Store — Knowledge Layer Persistence
=====================================================

Replaces JSON file storage with ChromaDB for:
- Semantic search over stored documents
- Automatic embedding via sentence-transformers
- Collection-based organization (signals, treaties, evidence)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Layer2_Knowledge.vector_store")

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except Exception as exc:  # Optional dependency or incompatible telemetry extras.
    chromadb = None
    ChromaSettings = None
    CHROMADB_AVAILABLE = False
    logger.warning("ChromaDB is unavailable; using the in-memory fallback: %s", exc)

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception as exc:  # Optional dependency for the Chroma backend only.
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers is unavailable; using the in-memory fallback: %s", exc)

class VectorStore:
    """Unified vector store backed by ChromaDB with embedding support."""

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        self.persist_dir = persist_dir or str(
            Path(__file__).resolve().parent.parent / "data" / "chroma"
        )
        self.embedding_model_name = embedding_model
        self._embedder = None
        self._client = None
        self._collections: Dict[str, Any] = {}
        self._fallback_documents: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._init()

    def _init(self) -> None:
        """Initialize ChromaDB client and embedding model."""
        if not CHROMADB_AVAILABLE or not SENTENCE_TRANSFORMERS_AVAILABLE:
            return
        try:
            os.makedirs(self.persist_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._embedder = SentenceTransformer(self.embedding_model_name)
            logger.info("ChromaDB initialized at %s", self.persist_dir)
            logger.info("Embedding model loaded: %s", self.embedding_model_name)
        except Exception as exc:
            self._client = None
            self._embedder = None
            logger.warning("Vector backend initialization failed; using in-memory fallback: %s", exc)

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts using sentence-transformers."""
        embeddings = self._embedder.encode(texts, show_progress_bar=False)
        return embeddings.tolist()

    def get_or_create_collection(self, name: str) -> Any:
        """Get existing collection or create new one."""
        if self._client is None:
            return self._fallback_documents.setdefault(name, {})
        if name in self._collections:
            return self._collections[name]

        collection = self._client.get_or_create_collection(name=name)
        self._collections[name] = collection
        return collection

    def store_document(
        self,
        collection_name: str,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a document with embeddings in a collection."""
        collection = self.get_or_create_collection(collection_name)
        if self._client is None:
            collection[doc_id] = {"text": text, "metadata": metadata or {}}
            return
        embedding = self._embed([text])[0]

        add_kwargs = {
            "ids": [doc_id],
            "embeddings": [embedding],
            "documents": [text],
        }
        if metadata:
            add_kwargs["metadatas"] = [metadata]
            
        collection.add(**add_kwargs)

    def search(
        self,
        collection_name: str,
        query: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Semantic search in a collection."""
        collection = self.get_or_create_collection(collection_name)
        if self._client is None:
            query_terms = set(query.lower().split())
            ranked = []
            for doc_id, document in collection.items():
                text = document["text"]
                text_terms = set(text.lower().split())
                overlap = len(query_terms & text_terms)
                if overlap:
                    ranked.append((overlap / max(len(query_terms), 1), doc_id, document))
            ranked.sort(key=lambda item: item[0], reverse=True)
            return [
                {"id": doc_id, "text": document["text"], "metadata": document["metadata"], "score": score}
                for score, doc_id, document in ranked[:k]
            ]

        embedding = self._embed([query])[0]
        results = collection.query(query_embeddings=[embedding], n_results=k)
        if not results or "documents" not in results:
            return []
            
        docs = results["documents"][0] if results["documents"] else []
        metas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results.get("distances", [[]])[0] if results.get("distances") else []
        
        return [
            {
                "id": results["ids"][0][i] if results.get("ids") else f"r{i}",
                "text": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else {},
                "score": 1.0 - (distances[i] if i < len(distances) else 0.0),
            }
            for i in range(min(k, len(docs)))
        ]

    def delete_collection(self, name: str) -> None:
        """Delete a collection."""
        if self._client is None:
            self._fallback_documents.pop(name, None)
            return
        try:
            self._client.delete_collection(name=name)
        except Exception:
            pass
        self._collections.pop(name, None)

    def list_collections(self) -> List[str]:
        """List all collection names."""
        if self._client is None:
            return list(self._fallback_documents)
        return [c.name for c in self._client.list_collections()]


# Module-level singleton
_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create the singleton vector store."""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
