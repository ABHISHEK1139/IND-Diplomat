"""
MoltBot Country Topic Map
===========================

Country-level search topics for the MoltBot OSINT sensor.

These are NOT signals.  These are **activity spaces** — broad queries
that capture the full spectrum of a country's observable behavior.

A single article retrieved by one topic often contains evidence for
MULTIPLE signals.  The observation extractor discovers those signals
after the text is fetched.

Design principle:
    Do NOT search for signals.
    Search for the country's activity space.
    Let the extractor decide what signals are present.
"""

from __future__ import annotations

from typing import Dict, List

# =====================================================================
# COUNTRY_TOPIC_MAP: country_iso → list of broad search topics
# =====================================================================
# Each topic should be:
#   - Concrete enough to return news articles
#   - Broad enough to catch multiple signals per article
#   - Phrased as a news editor would headline them
#
# The sensor will prepend the country name to each template at runtime,
# e.g. "Iran" + "military operations" → "Iran military operations"
# =====================================================================

COUNTRY_TOPIC_MAP: Dict[str, List[str]] = {
    "IRN": [
        "military operations",
        "Israel tensions",
        "protests unrest",
        "diplomacy negotiations",
        "cyber attack",
        "sanctions economy",
        "nuclear program",
        "missile drone strike",
    ],
    "ISR": [
        "military operations",
        "Iran tensions",
        "Gaza conflict",
        "diplomacy negotiations",
        "cyber attack",
        "defense deployment",
        "intelligence operations",
        "protests unrest",
    ],
    "RUS": [
        "military operations",
        "Ukraine conflict",
        "NATO tensions",
        "sanctions economy",
        "cyber attack",
        "diplomacy negotiations",
        "nuclear weapons",
        "protests unrest",
    ],
    "UKR": [
        "military operations",
        "Russia conflict",
        "NATO support",
        "sanctions economy",
        "cyber attack",
        "diplomacy negotiations",
        "drone strike",
        "internal politics",
    ],
    "CHN": [
        "military operations",
        "Taiwan tensions",
        "trade sanctions",
        "cyber espionage",
        "diplomacy negotiations",
        "South China Sea",
        "nuclear weapons",
        "protests unrest",
    ],
    "PRK": [
        "missile launch",
        "nuclear program",
        "military provocation",
        "sanctions economy",
        "diplomacy negotiations",
        "cyber attack",
        "internal politics",
        "South Korea tensions",
    ],
}

# =====================================================================
# Default topics — used for ANY country not explicitly mapped above
# =====================================================================
DEFAULT_TOPICS: List[str] = [
    "military operations",
    "conflict tensions",
    "protests unrest",
    "diplomacy negotiations",
    "sanctions economy",
    "cyber attack",
]


def get_topics(country_iso: str) -> List[str]:
    """
    Return search topic templates for a country.

    Parameters
    ----------
    country_iso : str
        ISO 3-letter code (e.g. "IRN").

    Returns
    -------
    list[str]
        Topic templates (without the country name prefix).
    """
    iso = country_iso.strip().upper()
    return COUNTRY_TOPIC_MAP.get(iso, DEFAULT_TOPICS)
