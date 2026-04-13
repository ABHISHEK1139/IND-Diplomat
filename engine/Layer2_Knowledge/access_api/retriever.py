"""
Diplomatic Retriever — Layer-2 Memory Search
==============================================
Pure retrieval — does NOT reason about queries.

Receives search instructions (QueryPlan) from Layer 3.
If no plan is provided, performs basic keyword search.

Layer 2 Rule: Retrieve on command. Never analyze intent.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

from engine.Layer2_Knowledge.vector_store import get_vector_store

# Optional dependencies - Lazy loaded
_nlp = None
_cross_encoder = None
_HAS_SPACY = False
_HAS_CROSS_ENCODER = False

# Try graph manager
try:
    from engine.Layer3_StateModel.binding.graph_manager import GraphManager
    _HAS_GRAPH = True
except ImportError:
    _HAS_GRAPH = False
    logger.info("[Retriever] GraphManager not available — graph search disabled")

# ═══════════════════════════════════════════════════════════════
# QueryPlan — lightweight data container
# The ACTUAL reasoning (building plans) happens in Layer 3.
# This is just the data shape so retriever knows what to search.
# ═══════════════════════════════════════════════════════════════
@dataclass
class QueryPlan:
    """Search instructions produced by Layer 3's query analyzer."""
    target_spaces: List[str] = field(default_factory=lambda: ["all"])
    countries: List[str] = field(default_factory=list)
    time_range: Optional[Tuple[str, str]] = None
    topic: str = ""
    query_type: str = "factual"
    original_query: str = ""
    confidence: float = 0.5


class DiplomaticRetriever:
    """
    Layer-2 memory retriever.
    Searches vector store and graph on command.
    Does NOT analyze intent — that is Layer 3's job.
    """

    def __init__(self):
        self.vector_store = get_vector_store()

        if _HAS_GRAPH:
            try:
                self.graph = GraphManager()
            except Exception:
                self.graph = None
                logger.info("[Retriever] Neo4j unavailable — graph search disabled")
        else:
            self.graph = None

    # ── Main search entry point ──────────────────────────────────

    def hybrid_search(
        self,
        query: str,
        plan: 'QueryPlan' = None,
        as_of_date: str = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Execute hybrid search pipeline.

        Layer 3 provides the QueryPlan (analyzed intent).
        If no plan is given, does basic keyword search (no reasoning).

        Args:
            query:       Natural language question.
            plan:        QueryPlan from Layer 3 (optional).
            as_of_date:  Optional date filter (ISO format).
            top_k:       Number of final results.

        Returns:
            List of result dicts: {id, content, metadata, score, ...}
        """
        # If no plan from L3, create minimal default (no reasoning)
        if plan is None:
            plan = QueryPlan(
                target_spaces=["all"],
                countries=[],
                original_query=query,
            )

        logger.info(
            "[Retriever] Searching: spaces=%s, countries=%s, "
            "time=%s, type=%s, topic=%s",
            plan.target_spaces, plan.countries,
            plan.time_range, plan.query_type, plan.topic,
        )

        # 1. Vector search — targeted by knowledge spaces
        vector_results = self._targeted_vector_search(plan, top_k * 2)

        # 2. Graph search (if Neo4j available)
        graph_results = self._graph_search(plan, as_of_date)

        # 3. RRF Fusion
        aggregated = {"vector": vector_results, "graph": graph_results}
        fused = self.reciprocal_rank_fusion(aggregated)

        # 4. Time filter (post-retrieval)
        if plan.time_range or as_of_date:
            fused = self._apply_time_filter(fused, plan.time_range, as_of_date)

        # 5. Cross-encoder reranking
        reranked = self.cross_encoder_rerank(query, fused, top_k=top_k)

        return reranked

    # ── Targeted vector search ───────────────────────────────────

    def _targeted_vector_search(
        self, plan: QueryPlan, top_k: int
    ) -> List[Dict[str, Any]]:
        """Search vector store, targeting plan's knowledge spaces."""
        all_results = []

        for space in plan.target_spaces:
            results = self.vector_store.search(
                query=plan.original_query,
                space=space,
                top_k=top_k,
            )
            all_results.extend(results)

        return all_results

    # ── Graph search ─────────────────────────────────────────────

    def _graph_search(
        self, plan: QueryPlan, as_of_date: str = None
    ) -> List[Dict[str, Any]]:
        """Search Neo4j graph for relational data."""
        if not self.graph or not self.graph.is_connected():
            return []

        results = []
        entities = plan.countries or self._extract_entities(plan.original_query)

        for entity_name in entities:
            if isinstance(entity_name, dict):
                entity_name = entity_name.get("text", "")
            try:
                graph_data = self.graph.temporal_traversal(
                    as_of_date or "2025-01-01",
                    entity_name,
                )
                for idx, item in enumerate(graph_data):
                    results.append({
                        "id":      f"graph_{entity_name}_{idx}",
                        "content": f"Treaty: {item.get('treaty', 'N/A')}, "
                                   f"Signed: {item.get('signed', 'N/A')}",
                        "metadata": {
                            "source": "graph",
                            "type":   "relational",
                            "entity": entity_name,
                        },
                    })
            except Exception as exc:
                logger.warning("[Retriever] Graph search failed for %s: %s", entity_name, exc)

        return results

    # ── Entity extraction ────────────────────────────────────────

    def extract_entities(self, query: str) -> List[Dict[str, str]]:
        """Extract named entities from query."""
        return self._extract_entities(query)

    def _extract_entities(self, query: str) -> List[Dict[str, str]]:
        """Extract named entities using spaCy or keyword fallback."""
        global _nlp, _HAS_SPACY
        entities = []

        # Lazy load spaCy
        if _nlp is None:
             try:
                 import spacy
                 _nlp = spacy.load("en_core_web_sm")
                 _HAS_SPACY = True
             except Exception:
                 _HAS_SPACY = False

        if _HAS_SPACY and _nlp:
            doc = _nlp(query)
            for ent in doc.ents:
                entities.append({"text": ent.text, "label": ent.label_})
        else:
            # Keyword fallback
            keywords = [
                "India", "China", "USA", "EU", "UN", "WTO",
                "RCEP", "NATO", "ASEAN", "BRICS", "Russia",
                "Pakistan", "Japan", "Australia",
            ]
            for kw in keywords:
                if kw.lower() in query.lower():
                    entities.append({"text": kw, "label": "GPE"})

        return entities

    # ── RRF Fusion ───────────────────────────────────────────────

    def reciprocal_rank_fusion(
        self,
        results: Dict[str, List[Any]],
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        Fuse rankings from multiple retrievers using RRF.
        Formula: score = sum(1 / (k + rank))
        """
        fused_scores = {}

        for source, items in results.items():
            for rank, item in enumerate(items):
                doc_id = item.get("id") or item.get("content", "")[:50]
                if doc_id not in fused_scores:
                    fused_scores[doc_id] = {"doc": item, "score": 0.0}
                fused_scores[doc_id]["score"] += 1.0 / (k + rank + 1)

        reranked = sorted(
            fused_scores.values(), key=lambda x: x["score"], reverse=True
        )
        return [item["doc"] for item in reranked]

    # ── Cross-encoder reranking ──────────────────────────────────

    def cross_encoder_rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Rerank documents using Cross-Encoder for improved precision."""
        global _cross_encoder, _HAS_CROSS_ENCODER

        # Lazy load CrossEncoder
        if _cross_encoder is None:
             try:
                 from sentence_transformers import CrossEncoder
                 _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                 _HAS_CROSS_ENCODER = True
             except Exception:
                 _HAS_CROSS_ENCODER = False

        if not _HAS_CROSS_ENCODER or not documents:
            return documents[:top_k]

        pairs = [(query, doc.get("content", "")) for doc in documents]

        try:
            scores = _cross_encoder.predict(pairs)
            scored_docs = list(zip(documents, scores))
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            return [doc for doc, _ in scored_docs[:top_k]]
        except Exception as exc:
            logger.warning("[Retriever] Cross-encoder failed: %s", exc)
            return documents[:top_k]

    # ── Time filtering ───────────────────────────────────────────

    def _apply_time_filter(
        self,
        documents: List[Dict],
        time_range: Optional[tuple] = None,
        as_of_date: str = None,
    ) -> List[Dict]:
        """Filter documents by time range from query plan."""
        if not time_range and not as_of_date:
            return documents

        start_date = None
        end_date = None

        if time_range:
            start_date, end_date = time_range
        elif as_of_date:
            end_date = as_of_date

        filtered = []
        for doc in documents:
            meta = doc.get("metadata", {})
            doc_date = meta.get("publication_date", "")

            if not doc_date:
                # Keep documents without dates (might still be relevant)
                filtered.append(doc)
                continue

            # String comparison works for ISO dates
            if start_date and doc_date < start_date:
                continue
            if end_date and doc_date > end_date:
                continue

            filtered.append(doc)

        # If time filter removed everything, return originals
        # (better to have some results than none)
        return filtered if filtered else documents

    # ── Utility ──────────────────────────────────────────────────

    @staticmethod
    def _parse_date(date_str: str):
        """Parse date string to datetime."""
        from datetime import datetime
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None


__all__ = ["DiplomaticRetriever"]
