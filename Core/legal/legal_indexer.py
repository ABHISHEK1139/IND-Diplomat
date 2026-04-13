"""
Core.legal.legal_indexer  —  Structure-Aware Legal Index Builder
================================================================

Rebuilds ChromaDB ``legal_articles`` collection using the structure-
aware splitter. Each chunk carries rich metadata (treaty_name,
article_number, domain, country, year) and is content-deduplicated
so identical text from different file paths is stored exactly once.
"""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Lazy imports ──────────────────────────────────────────────────────
# chromadb and sentence_transformers are HEAVY dependencies that may not
# be installed in every environment.  We import them lazily so that
# *other* modules (e.g. rag_bridge) can import this file's query_legal_articles()
# without failing at module load time.  The actual libraries are loaded
# on first use inside the functions that need them.

_chromadb = None
_SentenceTransformer = None


def _ensure_chromadb():
    global _chromadb
    if _chromadb is None:
        try:
            import chromadb as _cb
            _chromadb = _cb
        except ImportError:
            raise ImportError(
                "chromadb is required for the legal index. "
                "Install with: pip install chromadb"
            )
    return _chromadb


def _ensure_sentence_transformers():
    global _SentenceTransformer
    if _SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer as _ST
            _SentenceTransformer = _ST
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for the legal index. "
                "Install with: pip install sentence-transformers"
            )
    return _SentenceTransformer


from config.paths import LEGAL_MEMORY_PATH
from project_root import DATA_DIR


# ── Helpers ───────────────────────────────────────────────────────────

def _chroma_path() -> str:
    return os.getenv("CHROMA_DATA_DIR", str(DATA_DIR / "chroma"))


def _content_id(text: str) -> str:
    """Content-based dedup: same text → same id regardless of source."""
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return f"legal_{digest}"


def _source_root(source_path: str) -> str:
    try:
        rel = Path(source_path).resolve().relative_to(LEGAL_MEMORY_PATH.resolve())
        return rel.parts[0] if rel.parts else "unknown"
    except Exception:
        return "unknown"


@lru_cache(maxsize=1)
def _get_client():
    chromadb = _ensure_chromadb()
    return chromadb.PersistentClient(path=_chroma_path())


def _get_collection(client):
    return client.get_or_create_collection(
        name="legal_articles",
        metadata={"hnsw:space": "cosine"},
    )


@lru_cache(maxsize=1)
def _get_embedder():
    SentenceTransformer = _ensure_sentence_transformers()
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    def _load(device: str):
        return SentenceTransformer(
            "all-MiniLM-L6-v2",
            device=device,
            local_files_only=True,
        )

    try:
        import torch
        if torch.cuda.is_available():
            try:
                return _load("cuda")
            except RuntimeError as exc:
                if "out of memory" in str(exc).lower():
                    torch.cuda.empty_cache()
                    print("Embedder GPU OOM -> falling back to CPU")
                else:
                    raise
        return _load("cpu")
    except Exception:
        return _load("cpu")


def _discover_legal_roots() -> Tuple[str, ...]:
    return tuple(
        sorted(p.name for p in LEGAL_MEMORY_PATH.iterdir() if p.is_dir())
    )


# ── Index Builder ─────────────────────────────────────────────────────

def build_legal_index(
    include_nested: bool = True,
    batch_size: int = 128,
    roots: Optional[Tuple[str, ...]] = None,
    ocr_fallback: bool = True,
    wipe_first: bool = False,
) -> Tuple[int, int]:
    """
    Build the legal article index with structure-aware chunking.

    Deduplication is ALWAYS enabled (content-based SHA-1).
    Rich metadata is stored with every chunk.

    Args:
        wipe_first: If True, deletes the old collection before indexing.

    Returns:
        (indexed_articles, document_count)
    """
    # Lazy imports — only needed for indexing, not querying
    from core.legal.legal_loader import LegalLoader
    from core.legal.legal_splitter import split_legal_document

    selected_roots = roots or _discover_legal_roots()

    model = _get_embedder()

    loader = LegalLoader(
        include_nested=include_nested,
        use_gpu=False,
        roots=selected_roots,
        ocr_fallback=ocr_fallback,
    )
    docs = loader.load()
    client = _get_client()

    # Optionally wipe old collection for a clean rebuild
    if wipe_first:
        try:
            client.delete_collection("legal_articles")
            print("[INDEXER] Wiped old legal_articles collection")
        except Exception:
            pass

    collection = _get_collection(client)

    ids: List[str] = []
    docs_batch: List[str] = []
    embeddings: List[List[float]] = []
    metadatas: List[Dict] = []

    total_indexed = 0
    unique_articles = 0
    dupes_skipped = 0
    docs_with_chunks = 0
    docs_without_chunks = 0
    seen_hashes: set = set()

    for source_path, text in docs.items():
        root = _source_root(source_path)
        chunks = split_legal_document(text, source_path=source_path, root=root)

        if not chunks:
            docs_without_chunks += 1
            continue
        docs_with_chunks += 1

        # Batch embed all chunk texts at once
        chunk_texts = [c.text for c in chunks]
        chunk_embeddings = model.encode(
            chunk_texts,
            batch_size=64,
            show_progress_bar=False,
            convert_to_numpy=True,
        ).tolist()

        for chunk, emb in zip(chunks, chunk_embeddings):
            # Content-based dedup
            cid = _content_id(chunk.text)
            if cid in seen_hashes:
                dupes_skipped += 1
                continue
            seen_hashes.add(cid)

            # Build rich metadata (ChromaDB requires flat string/int/float values)
            meta = {
                "source": source_path,
                "root": root,
                "type": chunk.chunk_type,
                "heading": chunk.heading or "",
                "article_number": chunk.article_number or "",
                "parent_heading": chunk.parent_heading or "",
                "position": chunk.position,
                "treaty_name": chunk.metadata.get("treaty_name", ""),
                "year": chunk.metadata.get("year", ""),
                "domain": chunk.metadata.get("domain", ""),
                "country": chunk.metadata.get("country", ""),
            }

            ids.append(cid)
            docs_batch.append(chunk.text)
            embeddings.append(emb)
            metadatas.append(meta)
            unique_articles += 1

            if len(ids) >= batch_size:
                collection.upsert(
                    ids=ids,
                    documents=docs_batch,
                    embeddings=embeddings,
                    metadatas=metadatas,
                )
                total_indexed += len(ids)
                ids, docs_batch, embeddings, metadatas = [], [], [], []

    if ids:
        collection.upsert(
            ids=ids,
            documents=docs_batch,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        total_indexed += len(ids)

    print(f"\n{'='*60}")
    print(f" LEGAL INDEX BUILD COMPLETE")
    print(f"{'='*60}")
    print(f" Documents loaded:     {len(docs)}")
    print(f" Documents with chunks:{docs_with_chunks}")
    print(f" Documents empty:      {docs_without_chunks}")
    print(f" Unique chunks stored: {unique_articles}")
    print(f" Duplicates skipped:   {dupes_skipped}")
    print(f" Roots: {', '.join(selected_roots)}")
    print(f" Chroma: {_chroma_path()}")
    print(f" Collection count:     {collection.count()}")
    print(f"{'='*60}\n")

    return total_indexed, len(docs)


# ── Query API (unchanged interface) ───────────────────────────────────

def query_legal_articles(
    query: str,
    n_results: int = 3,
    where: Optional[Dict] = None,
) -> Dict:
    """
    Query the legal_articles collection.

    Accepts optional ``where`` filter for metadata-based filtering, e.g.:
        {"domain": "maritime"} or {"root": "global"}
    """
    model = _get_embedder()
    client = _get_client()
    collection = client.get_or_create_collection(
        name="legal_articles",
        metadata={"hnsw:space": "cosine"},
    )

    if collection.count() == 0:
        return {"documents": [[]], "metadatas": [[]]}

    emb = model.encode(query).tolist()
    query_args = {"query_embeddings": [emb], "n_results": n_results}
    if where:
        query_args["where"] = where
    return collection.query(**query_args)
