"""
Query Analyzer — Intelligent Query Understanding
==================================================
Analyzes user queries before retrieval to determine:
    - target knowledge spaces
    - countries mentioned
    - time range
    - query type (factual, analytical, comparative, temporal)
    - topic

This turns naive search(question) into
    search(spaces, countries, time_range, topic)
which dramatically improves retrieval accuracy.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════
# Query Plan — output of analysis
# ═════════════════════════════════════════════════════════════════

@dataclass
class QueryPlan:
    """Result of query analysis — guides retrieval strategy."""
    target_spaces: List[str]                     # ["legal", "event", ...]
    countries: List[str]                         # ["India", "China", ...]
    time_range: Optional[Tuple[str, str]] = None # ("2020-01-01", "2024-12-31")
    topic: str = ""                              # "trade", "security", etc.
    query_type: str = "factual"                  # factual|analytical|comparative|temporal
    original_query: str = ""
    confidence: float = 0.5


# ═════════════════════════════════════════════════════════════════
# Reference Data
# ═════════════════════════════════════════════════════════════════

# Country keywords for detection
_COUNTRIES = {
    "india": "India", "china": "China", "usa": "United States",
    "united states": "United States", "u.s.": "United States",
    "america": "United States", "russia": "Russia", "pakistan": "Pakistan",
    "japan": "Japan", "australia": "Australia", "uk": "United Kingdom",
    "united kingdom": "United Kingdom", "france": "France",
    "germany": "Germany", "brazil": "Brazil", "south africa": "South Africa",
    "canada": "Canada", "israel": "Israel", "iran": "Iran",
    "saudi arabia": "Saudi Arabia", "turkey": "Turkey", "türkiye": "Turkey",
    "south korea": "South Korea", "north korea": "North Korea",
    "indonesia": "Indonesia", "bangladesh": "Bangladesh",
    "sri lanka": "Sri Lanka", "nepal": "Nepal", "myanmar": "Myanmar",
    "afghanistan": "Afghanistan", "iraq": "Iraq", "syria": "Syria",
    "ukraine": "Ukraine", "taiwan": "Taiwan", "philippines": "Philippines",
    "vietnam": "Vietnam", "thailand": "Thailand", "singapore": "Singapore",
    "eu": "European Union", "european union": "European Union",
    "asean": "ASEAN", "nato": "NATO", "brics": "BRICS",
    "quad": "QUAD", "g7": "G7", "g20": "G20",
}

# Topic triggers → knowledge space mapping
_TOPIC_SPACE_MAP = {
    "trade":       "economic",
    "tariff":      "economic",
    "sanction":    "economic",
    "export":      "economic",
    "import":      "economic",
    "investment":  "economic",
    "fdi":         "economic",
    "gdp":         "economic",
    "inflation":   "economic",
    "treaty":      "legal",
    "law":         "legal",
    "convention":  "legal",
    "agreement":   "legal",
    "resolution":  "legal",
    "jurisdiction":"legal",
    "sovereignty": "legal",
    "territorial": "legal",
    "unclos":      "legal",
    "eez":         "legal",
    "military":    "strategic",
    "defence":     "strategic",
    "defense":     "strategic",
    "nuclear":     "strategic",
    "missile":     "strategic",
    "security":    "strategic",
    "alliance":    "strategic",
    "geopolitical":"strategic",
    "strategy":    "strategic",
    "maritime":    "strategic",
    "indo-pacific":"strategic",
}

# Query type detection patterns
_ANALYTICAL_PATTERNS = [
    "why", "how does", "what impact", "what effect",
    "analyze", "explain", "implications", "consequences",
    "significance", "interpret",
]

_COMPARATIVE_PATTERNS = [
    "compare", "vs", "versus", "difference between",
    "how does.*differ", "contrast",
]

_TEMPORAL_PATTERNS = [
    "how has.*changed", "evolution of", "history of",
    "since when", "when did", "timeline",
    "before and after", "over time", "progression",
]

# Time reference detection
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_RELATIVE_TIME = {
    "last year":     1,
    "past year":     1,
    "last 2 years":  2,
    "last two years":2,
    "past 2 years":  2,
    "last 3 years":  3,
    "last 5 years":  5,
    "past 5 years":  5,
    "last decade":   10,
    "past decade":   10,
    "last month":    0.08,  # ~1 month
    "recent":        0.5,   # ~6 months
    "recently":      0.5,
    "current":       1,
    "this year":     1,
}


# ═════════════════════════════════════════════════════════════════
# Query Analyzer
# ═════════════════════════════════════════════════════════════════

class QueryAnalyzer:
    """
    Analyze query intent before retrieval.

    Transforms unstructured natural language queries into structured
    retrieval plans that guide the search system.
    """

    def analyze(self, query: str) -> QueryPlan:
        """
        Analyze a query and produce a retrieval plan.

        Args:
            query: Natural language question.

        Returns:
            QueryPlan with target_spaces, countries, time_range,
            topic, query_type.
        """
        query_lower = query.lower()

        countries = self._extract_countries(query_lower)
        time_range = self._extract_time_references(query_lower)
        topic, target_spaces = self._detect_topic_and_spaces(query_lower)
        query_type = self._detect_query_type(query_lower)

        # If no specific spaces detected, search all
        if not target_spaces:
            target_spaces = ["legal", "event", "economic", "strategic"]

        # Confidence based on how much we could determine
        confidence = 0.3
        if countries:
            confidence += 0.2
        if time_range:
            confidence += 0.2
        if topic:
            confidence += 0.15
        if len(target_spaces) < 4:
            confidence += 0.15  # Narrowed search is more confident

        return QueryPlan(
            target_spaces=target_spaces,
            countries=countries,
            time_range=time_range,
            topic=topic,
            query_type=query_type,
            original_query=query,
            confidence=round(confidence, 2),
        )

    # ── Country extraction ───────────────────────────────────────

    def _extract_countries(self, query_lower: str) -> List[str]:
        """Extract country/bloc mentions from query."""
        found = []
        for keyword, country in _COUNTRIES.items():
            # Word boundary matching to avoid partial matches
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, query_lower) and country not in found:
                found.append(country)
        return found

    # ── Time reference extraction ────────────────────────────────

    def _extract_time_references(self, query_lower: str) -> Optional[Tuple[str, str]]:
        """
        Parse temporal references from query.

        Handles:
            - Explicit years: "in 2020", "from 2018 to 2023"
            - Relative: "last 5 years", "recent", "this year"
            - Era references: "before COVID", "post-Modi"
        """
        today = date.today()

        # Check for explicit year ranges: "from 2018 to 2023"
        range_match = re.search(
            r"(?:from|between)\s+((?:19|20)\d{2})\s+(?:to|and)\s+((?:19|20)\d{2})",
            query_lower,
        )
        if range_match:
            return (f"{range_match.group(1)}-01-01", f"{range_match.group(2)}-12-31")

        # Check for relative time references
        for phrase, years_back in _RELATIVE_TIME.items():
            if phrase in query_lower:
                start = today - timedelta(days=int(years_back * 365))
                return (start.isoformat(), today.isoformat())

        # Check for single year mentions
        years = _YEAR_RE.findall(query_lower)
        if years:
            years_int = sorted(set(int(f"{c}{y}") for c, y in [(y[:2], y[2:]) for y in years]))
            # Wait, the regex captures 2-char groups. Let me fix:
            years_int = sorted(set(int(y) for y in _YEAR_RE.findall(query_lower) 
                                   if len(y) == 2))
            # Actually the regex returns full matches:
            year_matches = [m for m in re.finditer(r"\b((?:19|20)\d{2})\b", query_lower)]
            years_int = sorted(set(int(m.group(1)) for m in year_matches))
            
            if len(years_int) >= 2:
                return (f"{years_int[0]}-01-01", f"{years_int[-1]}-12-31")
            elif len(years_int) == 1:
                return (f"{years_int[0]}-01-01", f"{years_int[0]}-12-31")

        # Era references
        era_patterns = {
            "pre-covid":   ("2015-01-01", "2020-01-01"),
            "before covid":("2015-01-01", "2020-01-01"),
            "post-covid":  ("2020-03-01", today.isoformat()),
            "after covid":  ("2020-03-01", today.isoformat()),
            "cold war":    ("1947-01-01", "1991-12-31"),
            "post-cold war":("1992-01-01", "2001-09-10"),
        }
        for pattern, range_val in era_patterns.items():
            if pattern in query_lower:
                return range_val

        return None

    # ── Topic and space detection ────────────────────────────────

    def _detect_topic_and_spaces(
        self, query_lower: str
    ) -> Tuple[str, List[str]]:
        """Detect topic keywords and map to knowledge spaces."""
        space_scores: Dict[str, int] = {}
        detected_topic = ""
        best_score = 0

        for keyword, space in _TOPIC_SPACE_MAP.items():
            if keyword in query_lower:
                space_scores[space] = space_scores.get(space, 0) + 1
                if space_scores[space] > best_score:
                    best_score = space_scores[space]
                    detected_topic = keyword

        if space_scores:
            # Return top-scoring spaces (with at least half of max score)
            max_score = max(space_scores.values())
            threshold = max(1, max_score // 2)
            target_spaces = [
                s for s, score in space_scores.items() if score >= threshold
            ]
            return detected_topic, target_spaces

        return "", []

    # ── Query type classification ────────────────────────────────

    def _detect_query_type(self, query_lower: str) -> str:
        """Classify query intent."""
        for pattern in _TEMPORAL_PATTERNS:
            if re.search(pattern, query_lower):
                return "temporal"

        for pattern in _COMPARATIVE_PATTERNS:
            if re.search(pattern, query_lower):
                return "comparative"

        for pattern in _ANALYTICAL_PATTERNS:
            if pattern in query_lower:
                return "analytical"

        # Default
        return "factual"


# ── Module-level convenience ─────────────────────────────────────

query_analyzer = QueryAnalyzer()

__all__ = ["QueryAnalyzer", "query_analyzer", "QueryPlan"]
