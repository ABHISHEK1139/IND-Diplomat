"""Validate embedding + ChromaDB storage/retrieval path."""

from __future__ import annotations

import math
import sys
import chromadb
from sentence_transformers import SentenceTransformer


def fail(reason: str) -> int:
    print(f"RAG_FAILED: {reason}")
    return 1


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def main() -> int:
    text = "Escalation risk rises when military drills, hostile rhetoric, and failed talks align."
    try:
        model = SentenceTransformer("all-MiniLM-L6-v2")
        embedding = model.encode(text).tolist()
    except Exception as exc:
        return fail(f"Embedding generation failed: {exc}")

    try:
        client = chromadb.EphemeralClient()
        collection = client.get_or_create_collection(
            name="bootstrap_rag_check",
            metadata={"hnsw:space": "cosine"},
        )
        collection.upsert(
            ids=["doc1"],
            documents=[text],
            embeddings=[embedding],
            metadatas=[{"source": "bootstrap"}],
        )
        result = collection.query(
            query_embeddings=[embedding],
            n_results=1,
            include=["documents", "embeddings"],
        )
    except Exception as exc:
        return fail(f"ChromaDB storage/retrieval failed: {exc}")

    docs_all = result.get("documents")
    embeds_all = result.get("embeddings")
    if docs_all is None or len(docs_all) == 0 or len(docs_all[0]) == 0:
        return fail("ChromaDB returned empty retrieval payload")
    if embeds_all is None or len(embeds_all) == 0 or len(embeds_all[0]) == 0:
        return fail("ChromaDB returned empty embedding payload")

    retrieved_doc = docs_all[0][0]
    retrieved_embedding = embeds_all[0][0]
    if hasattr(retrieved_embedding, "tolist"):
        retrieved_embedding = retrieved_embedding.tolist()
    score = cosine(embedding, retrieved_embedding)

    if score < 0.6:
        return fail(f"Similarity below threshold: {score:.4f}")

    print(f"RAG_OK: similarity={score:.4f}")
    print(f"RAG_DOC: {retrieved_doc[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
