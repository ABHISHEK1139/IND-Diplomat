"""
Legal Indexer — Live Web Search via DuckDuckGo
================================================

Replaces the old ChromaDB-based local treaty index with live
DuckDuckGo web search. No local files, no OCR, no embeddings needed.

The query_legal_articles() interface is preserved for backward
compatibility with the rest of the pipeline.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

logger = logging.getLogger("Legal.indexer")

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    logger.info("duckduckgo-search not installed. query_legal_articles will return empty results.")


def query_legal_articles(
    query: str,
    n_results: int = 3,
    where: Optional[Dict] = None,
) -> Dict:
    """Query for legal articles using DuckDuckGo web search.

    This replaces the old ChromaDB vector search. The interface
    is kept identical so existing callers don't need to change.

    Args:
        query: The legal/treaty search query.
        n_results: Number of results to return.
        where: Optional metadata filter (ignored in web search mode).

    Returns:
        Dict with 'documents' and 'metadatas' keys matching the old ChromaDB format.
    """
    if not DDGS_AVAILABLE:
        return {"documents": [[]], "metadatas": [[]]}

    try:
        ddgs = DDGS()
        search_query = f"{query} international treaty law legal article"
        results = list(ddgs.text(search_query, max_results=n_results, region="wt-wt"))

        documents = []
        metadatas = []

        for r in results:
            documents.append(r.get("body", ""))
            metadatas.append({
                "treaty_name": r.get("title", "Unknown"),
                "article": "See source",
                "source": r.get("href", "DuckDuckGo"),
                "domain": where.get("domain", "") if where else "",
            })

        return {"documents": [documents], "metadatas": [metadatas]}

    except Exception as e:
        logger.warning("DuckDuckGo legal search failed: %s", e)
        return {"documents": [[]], "metadatas": [[]]}


def build_legal_index(**kwargs):
    """No-op. Legal index is now powered by live web search.

    Kept for backward compatibility — calling this function
    does nothing and returns (0, 0).
    """
    logger.info("build_legal_index() is a no-op. Legal RAG now uses live DuckDuckGo search.")
    return (0, 0)
