from datetime import datetime
from typing import Any, Dict, List, Tuple
import math


class ReliabilityScorer:
    """
    Heuristic reliability scorer.
    Factors:
      - provenance (dossier > neo4j > web/unknown)
      - recency (newer is better)
      - retrieval score when present
    """

    def _recency_score(self, date_str: str) -> float:
        if not date_str:
            return 0.5
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", ""))
            days = (datetime.utcnow() - dt).days
            if days < 180:
                return 1.0
            if days < 365:
                return 0.85
            if days < 5 * 365:
                return 0.7
            return 0.5
        except Exception:
            return 0.5

    def _provenance_score(self, metadata: Dict[str, Any]) -> float:
        source = str(metadata.get("source", "")).lower()
        if source == "dossier":
            return 1.0
        if source == "neo4j":
            return 0.9
        if "gov" in source or "official" in source:
            return 0.85
        if "news" in source:
            return 0.65
        return 0.55

    def score_sources(self, sources: List[Dict[str, Any]], query: str) -> Tuple[List[Dict[str, Any]], float]:
        ledger = []
        total = 0.0
        for src in sources:
            meta = src.get("metadata", {}) or {}
            provenance = self._provenance_score(meta)
            recency = self._recency_score(meta.get("as_of") or meta.get("date"))
            retrieval = float(src.get("score", meta.get("score", 0.6)) or 0.6)
            score = round((provenance * 0.45) + (recency * 0.35) + (retrieval * 0.20), 3)
            ledger.append(
                {
                    "id": src.get("id"),
                    "source": meta.get("source"),
                    "provenance": provenance,
                    "recency": recency,
                    "retrieval": retrieval,
                    "composite": score,
                    "content_preview": (src.get("content", "") or "")[:160],
                }
            )
            total += score

        aggregate = round(total / len(ledger), 3) if ledger else 0.5
        return ledger, aggregate
