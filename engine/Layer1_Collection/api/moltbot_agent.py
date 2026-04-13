"""
MoltBot Agent — Facade for the MoltBot Web Sensor
====================================================

This module exists so that legacy import paths still work:

    from engine.Layer1_Collection.api.moltbot_agent import moltbot_agent
    docs = moltbot_agent.collect_documents(query=..., ...)

Under the hood it delegates to the real sensor:
    Layer1_Collection.sensors.moltbot_sensor

The sensor:
    1. Converts signals → search queries (mapping table, no LLM)
    2. Searches web (DuckDuckGo / Bing RSS)
    3. Fetches articles (requests + BeautifulSoup)
    4. Extracts observations (regex pattern matching)
    5. Returns structured evidence for the Belief Accumulator
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Layer1.api.moltbot_agent")

# ── Lazy import to avoid circular dependency ────────────────────
_sensor = None


def _get_sensor():
    global _sensor
    if _sensor is None:
        from engine.Layer1_Collection.sensors.moltbot_sensor import moltbot_sensor
        _sensor = moltbot_sensor
    return _sensor


class MoltBotAgent:
    """
    Agent interface for MoltBot web sensor.

    Provides the ``collect_documents()`` API expected by:
        - ``Core.intelligence.moltbot_adapter._try_moltbot()``
        - ``Core.intelligence.collection_bridge.execute_collection_plan()``
    """

    def collect_documents(
        self,
        query: str = "",
        required_evidence: Optional[List[str]] = None,
        countries: Optional[List[str]] = None,
        missing_gaps: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Collect documents from the web for the given query / signals.

        Parameters
        ----------
        query : str
            Free-text search query.
        required_evidence : list[str]
            Signal codes that are required (e.g. ["SIG_MIL_ESCALATION"]).
        countries : list[str]
            Country names/codes to scope the search.
        missing_gaps : list[str]
            Signal codes representing intelligence gaps.
        limit : int
            Maximum documents to return.

        Returns
        -------
        list[dict]
            Document dicts with: content, text, url, title, date,
            source_url, metadata, raw_observation.
        """
        sensor = _get_sensor()
        return sensor.collect_documents(
            query=query,
            required_evidence=required_evidence,
            countries=countries,
            missing_gaps=missing_gaps,
            limit=limit,
        )

    def sense(
        self,
        signals: List[str],
        country: str = "",
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Run structured sensor sweep for given signals.

        Returns observation dicts in GDELT-compatible format.
        """
        sensor = _get_sensor()
        return sensor.sense(signals=signals, country=country, **kwargs)


# Singleton — this is what callers import
moltbot_agent = MoltBotAgent()

__all__ = ["MoltBotAgent", "moltbot_agent"]
