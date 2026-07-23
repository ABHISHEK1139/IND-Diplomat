"""
Legal Treaty RAG Pipeline — Live Internet Search via DuckDuckGo
================================================================

Searches for treaty text, international law, and legal precedents
in real-time using DuckDuckGo. No local treaty PDFs required.

Falls back to the hardcoded SIGNAL_TREATY_MAP in signal_legal_mapper.py
when internet search is unavailable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Legal.treaty_rag")

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    logger.info("duckduckgo-search not installed. Legal RAG will use heuristic fallback only.")

try:
    import litellm
except ImportError:
    litellm = None


class TreatyRAGPipeline:
    """RAG pipeline for treaty-aware geopolitical analysis using live web search."""

    def __init__(self):
        self._ddgs = DDGS() if DDGS_AVAILABLE else None

    def _search_web(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search DuckDuckGo for treaty and legal information."""
        if not self._ddgs:
            return []

        try:
            results = list(self._ddgs.text(
                query,
                max_results=max_results,
                region="wt-wt",  # Worldwide
            ))
            return [
                {
                    "title": r.get("title", ""),
                    "text": r.get("body", ""),
                    "url": r.get("href", ""),
                    "source": "DuckDuckGo",
                }
                for r in results
            ]
        except Exception as e:
            logger.warning("DuckDuckGo search failed: %s", e)
            return []

    async def search_treaties(
        self,
        query: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search for relevant treaty texts using DuckDuckGo.

        Constructs a targeted legal search query and returns
        web results with treaty-relevant content.
        """
        search_query = f"{query} international treaty law article text"
        results = self._search_web(search_query, max_results=k)

        # Enrich results with metadata
        enriched = []
        for r in results:
            enriched.append({
                "id": r.get("url", ""),
                "text": r.get("text", ""),
                "score": 0.7,  # Web results are assumed moderately relevant
                "metadata": {
                    "treaty_name": r.get("title", "Unknown"),
                    "article": "See source",
                    "source": r.get("url", "DuckDuckGo"),
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                },
            })
        return enriched

    async def analyze_signal(
        self,
        signal: Dict[str, Any],
        relevant_treaties: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze a geopolitical signal against relevant treaties.

        Uses DuckDuckGo to search for additional legal context when
        the hardcoded treaty map doesn't have enough information.

        Args:
            signal: {action, entity, target, intensity, ...}
            relevant_treaties: [{name, article, text, ...}] from signal mapper

        Returns:
            Legal analysis result
        """
        action = signal.get("action", "unknown_action")
        country = signal.get("country", "")
        target = signal.get("target", "")

        # If no treaties were found from the hardcoded map, search the web
        if not relevant_treaties:
            search_query = f"{action} {country} {target} international law treaty violation"
            web_results = self._search_web(search_query, max_results=3)

            if not web_results:
                return {
                    "relevant_treaties": [],
                    "compliance_assessment": "NOT_APPLICABLE",
                    "specific_violations": [],
                    "consultation_required": False,
                    "precedents": [],
                    "confidence": 0.0,
                    "legal_risks": ["No relevant treaties found for this signal."],
                }

            # Convert web results into treaty-like entries
            relevant_treaties = [
                {
                    "metadata": {
                        "treaty_name": r.get("title", "Unknown"),
                        "article": "See source",
                    },
                    "text": r.get("text", ""),
                    "url": r.get("url", ""),
                }
                for r in web_results
            ]

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
                "relevance": f"Signal '{action}' may relate to {treaty_name} {article}",
                "source_url": treaty.get("url", ""),
            })

            # Check for consultation requirements
            if any(word in text.lower() for word in ["consult", "notify", "inform", "prior"]):
                analysis["consultation_required"] = True
                analysis["legal_risks"].append(
                    f"{treaty_name} {article} may require prior consultation."
                )

            # Check for violation indicators
            if "deploy" in action.lower() or "mobilize" in action.lower():
                analysis["specific_violations"].append({
                    "article": f"{treaty_name} {article}",
                    "reason": "Military deployment without prior notification may violate consultation requirements.",
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


# Module-level singleton
_treaty_rag: Optional[TreatyRAGPipeline] = None


def get_treaty_rag() -> TreatyRAGPipeline:
    """Get or create the treaty RAG pipeline."""
    global _treaty_rag
    if _treaty_rag is None:
        _treaty_rag = TreatyRAGPipeline()
    return _treaty_rag
