"""
Legal Treaty RAG Pipeline — Haystack/ChromaDB Treaty Reasoning
===============================================================

The unique feature: maps geopolitical signals to specific treaty articles
and international law. Uses Haystack for RAG when available, falls back to
direct ChromaDB search.

Key capability: "Given India's troop movement, what does the India-Bhutan
Friendship Treaty Article 2 say?"
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Legal.treaty_rag")

try:
    from haystack import Pipeline as HaystackPipeline
    from haystack.components.retrievers import InMemoryBM25Retriever
    from haystack.components.builders import PromptBuilder
    from haystack.components.generators import OpenAIGenerator
    from haystack.document_stores.in_memory import InMemoryDocumentStore
    from haystack import Document
    HAYSTACK_AVAILABLE = True
except ImportError:
    HAYSTACK_AVAILABLE = False
    logger.info("Haystack not installed. Using direct ChromaDB search for legal RAG.")


LEGAL_PROMPT_TEMPLATE = """
You are a legal expert analyzing geopolitical signals against international treaties and law.

CONTEXT (relevant treaty text):
{% for doc in documents %}
  TREATY: {{ doc.meta.get('treaty_name', 'Unknown') }}
  ARTICLE: {{ doc.meta.get('article', 'Unknown') }}
  TEXT: {{ doc.content }}
{% endfor %}

SIGNAL BEING ANALYZED:
{{ query }}

INSTRUCTIONS:
1. Identify which treaty articles are relevant to this signal
2. State whether the action described is consistent with or violates the treaty
3. Cite the specific article and text
4. Note any precedents (ICJ rulings, UN resolutions) that apply
5. Flag if this action requires prior consultation or notification
6. NEVER speculate beyond what the treaty text supports

Return your analysis in this JSON format:
{
  "relevant_treaties": [{"name": "", "article": "", "relevance": ""}],
  "compliance_assessment": "CONSISTENT|VIOLATION|UNCLEAR|NOT_APPLICABLE",
  "specific_violations": [{"article": "", "reason": ""}],
  "consultation_required": true|false,
  "precedents": [{"case": "", "relevance": ""}],
  "confidence": 0.0,
  "legal_risks": [""]
}
"""


class TreatyRAGPipeline:
    """RAG pipeline for treaty-aware geopolitical analysis."""

    def __init__(self):
        self._haystack_pipeline = None
        self._init()

    def _init(self) -> None:
        """Initialize Haystack pipeline if available."""
        if HAYSTACK_AVAILABLE:
            try:
                doc_store = InMemoryDocumentStore()
                self._haystack_pipeline = HaystackPipeline()
                self._haystack_pipeline.add_component("retriever", InMemoryBM25Retriever(document_store=doc_store))
                self._haystack_pipeline.add_component("prompt_builder", PromptBuilder(template=LEGAL_PROMPT_TEMPLATE))
                logger.info("Haystack legal RAG pipeline initialized")
            except Exception as e:
                logger.warning("Haystack pipeline init failed: %s", e)
                self._haystack_pipeline = None

    async def analyze_signal(
        self,
        signal: Dict[str, Any],
        relevant_treaties: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze a geopolitical signal against relevant treaties.

        Args:
            signal: {action, entity, target, intensity, ...}
            relevant_treaties: [{name, article, text, ...}] from ChromaDB search

        Returns:
            Legal analysis result
        """
        if not relevant_treaties:
            return {
                "relevant_treaties": [],
                "compliance_assessment": "NOT_APPLICABLE",
                "specific_violations": [],
                "consultation_required": False,
                "precedents": [],
                "confidence": 0.0,
                "legal_risks": ["No relevant treaties found for this signal."],
            }

        # Build structured analysis from treaty matches
        analysis = {
            "relevant_treaties": [],
            "compliance_assessment": "UNCLEAR",
            "specific_violations": [],
            "consultation_required": False,
            "precedents": [],
            "confidence": 0.5,
            "legal_risks": [],
        }

        for treaty in relevant_treaties:
            treaty_name = treaty.get("metadata", {}).get("treaty_name", treaty.get("name", "Unknown"))
            article = treaty.get("metadata", {}).get("article", "Unknown")
            text = treaty.get("text", "")

            analysis["relevant_treaties"].append({
                "name": treaty_name,
                "article": article,
                "relevance": f"Signal '{signal.get('action', '')}' may relate to {treaty_name} {article}",
            })

            # Check for consultation requirements
            if any(word in text.lower() for word in ["consult", "notify", "inform", "prior"]):
                analysis["consultation_required"] = True
                analysis["legal_risks"].append(
                    f"{treaty_name} {article} may require prior consultation."
                )

            # Check for violation indicators
            action = signal.get("action", "").lower()
            if "deploy" in action or "mobilize" in action:
                analysis["specific_violations"].append({
                    "article": f"{treaty_name} {article}",
                    "reason": f"Military deployment without prior notification may violate consultation requirements.",
                })

        # Determine overall compliance
        if analysis["specific_violations"]:
            analysis["compliance_assessment"] = "VIOLATION"
            analysis["confidence"] = 0.7
        elif analysis["consultation_required"]:
            analysis["compliance_assessment"] = "UNCLEAR"
            analysis["confidence"] = 0.5
        else:
            analysis["compliance_assessment"] = "CONSISTENT"
            analysis["confidence"] = 0.6

        return analysis

    async def search_treaties(
        self,
        query: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search relevant treaty texts for a query.

        Uses ChromaDB vector search via the shared VectorStore.
        """
        try:
            from dip.layer2_knowledge.vector_store import get_vector_store
            store = get_vector_store()
            return store.search("treaties", query, k=k)
        except ImportError:
            return []

    async def index_treaty(
        self,
        treaty_name: str,
        article: str,
        text: str,
        doc_id: Optional[str] = None,
    ) -> None:
        """Index a treaty article into the vector store."""
        try:
            from dip.layer2_knowledge.vector_store import get_vector_store
            store = get_vector_store()
            store.store_document(
                collection_name="treaties",
                doc_id=doc_id or f"{treaty_name}_{article}",
                text=text,
                metadata={
                    "treaty_name": treaty_name,
                    "article": article,
                    "indexed_at": datetime.now(timezone.utc).isoformat(),
                    "source": "DIP_8_legal_memory",
                },
            )
            logger.info("Indexed treaty: %s %s", treaty_name, article)
        except ImportError:
            logger.warning("VectorStore not available, skipping treaty index")


# Module-level singleton
_treaty_rag: Optional[TreatyRAGPipeline] = None


def get_treaty_rag() -> TreatyRAGPipeline:
    """Get or create the treaty RAG pipeline."""
    global _treaty_rag
    if _treaty_rag is None:
        _treaty_rag = TreatyRAGPipeline()
    return _treaty_rag
