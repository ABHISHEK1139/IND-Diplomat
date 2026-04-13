"""
Corroboration Engine — Multi-Source Claim Verification
=======================================================

Intelligence requires **independent corroboration** before treating
a signal as actionable.  A single news article claiming "Iran enriched
uranium" is journalism.  That same claim confirmed by IAEA + Reuters +
a government statement is intelligence.

This module provides *claim-level* verification:

    1. Extract the key claim from a critical observation
    2. Generate secondary search queries targeting independent sources
    3. Execute secondary searches (IAEA, Reuters, AP, official statements)
    4. Score corroboration level based on source diversity

Pipeline position::

    MoltBot observations
        → Belief Accumulator (observation-level corroboration)
            → **Corroboration Engine** (claim-level verification)  ← THIS MODULE
                → Enhanced beliefs with verification_status

Design constraints:
    - Rate-limited: max 3 secondary searches per signal per run
    - No LLM: uses pattern matching + search + counting
    - Graceful degrade: if secondary search fails, returns "unverified"
    - Budget-aware: respects max_total_searches cap

Usage
-----
    from Core.verification.corroboration_engine import verify_critical_claims

    enhanced_beliefs = verify_critical_claims(beliefs, country_iso="IRN")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("Core.verification.corroboration")


# =====================================================================
# Configuration
# =====================================================================

# Signals considered "critical" — worth the cost of secondary searches
CRITICAL_SIGNALS: Set[str] = {
    "SIG_MIL_ESCALATION",
    "SIG_WMD_RISK",
    "SIG_MIL_MOBILIZATION",
    "SIG_FORCE_POSTURE",
    "SIG_CYBER_ACTIVITY",
    "SIG_ALLIANCE_ACTIVATION",
}

# Maximum secondary searches per run (rate-limit budget)
MAX_SECONDARY_SEARCHES = 6

# Maximum secondary searches per signal
MAX_SEARCHES_PER_SIGNAL = 2

# Authoritative source patterns — used to classify secondary results
_AUTHORITATIVE_PATTERNS = {
    "official":    re.compile(r"IAEA|United Nations|UN Security|WHO|NATO|"
                              r"State Department|Foreign Ministry|MOD|"
                              r"Kremlin|White House|Pentagon|"
                              r"official\s+statement|press\s+briefing",
                              re.IGNORECASE),
    "wire":        re.compile(r"Reuters|Associated Press|AFP|AP News|"
                              r"Bloomberg|Agence France",
                              re.IGNORECASE),
    "quality":     re.compile(r"BBC|Al Jazeera|CNN|New York Times|"
                              r"Washington Post|Guardian|Financial Times|"
                              r"The Economist|Foreign Affairs|TASS|Xinhua",
                              re.IGNORECASE),
}


# =====================================================================
# Signal → secondary search queries
# =====================================================================

_VERIFICATION_QUERIES: Dict[str, List[str]] = {
    "SIG_WMD_RISK": [
        "{country} uranium enrichment IAEA report",
        "{country} nuclear program Reuters AP",
        "{country} IAEA inspection official statement",
    ],
    "SIG_MIL_ESCALATION": [
        "{country} military escalation Reuters AP",
        "{country} attack strike official confirmation",
        "{country} military operation UN statement",
    ],
    "SIG_MIL_MOBILIZATION": [
        "{country} military mobilization official",
        "{country} reservists deployed confirmation",
    ],
    "SIG_FORCE_POSTURE": [
        "{country} troop deployment satellite imagery",
        "{country} military exercise official announcement",
    ],
    "SIG_CYBER_ACTIVITY": [
        "{country} cyber attack attribution official",
        "{country} hacking campaign CISA advisory",
    ],
    "SIG_ALLIANCE_ACTIVATION": [
        "{country} alliance activation mutual defense",
        "{country} coalition deployment official",
    ],
}


# =====================================================================
# Core verification function
# =====================================================================

def verify_critical_claims(
    beliefs: List[Dict[str, Any]],
    country_iso: str = "",
    country_name: str = "",
    max_total_searches: int = MAX_SECONDARY_SEARCHES,
) -> List[Dict[str, Any]]:
    """
    Attempt secondary verification of critical-signal beliefs.

    For each critical belief, performs secondary web searches to find
    corroborating reports from authoritative sources (IAEA, Reuters,
    official statements, etc.).

    Parameters
    ----------
    beliefs : list[dict]
        Beliefs from ``BeliefAccumulator.evaluate()``.
    country_iso : str
        ISO-3 code of the target country.
    country_name : str
        Full country name for search queries.
    max_total_searches : int
        Global search budget cap.

    Returns
    -------
    list[dict]
        Same beliefs list, with enhanced ``verification_status``,
        ``secondary_sources``, and ``corroboration_detail`` fields
        for beliefs that were verified.
    """
    if not beliefs:
        return beliefs

    # Lazy imports — only load web search if we actually verify
    try:
        from engine.Layer1_Collection.sensors.moltbot_sensor import web_search
    except ImportError:
        logger.debug("[CORROBORATION] Cannot import web_search — skipping verification")
        return beliefs

    # Resolve country name
    if not country_name:
        country_name = _iso_to_name(country_iso)

    # Filter to critical signals only
    critical_beliefs = [
        b for b in beliefs
        if b.get("signal", "").upper() in CRITICAL_SIGNALS
    ]

    if not critical_beliefs:
        logger.debug("[CORROBORATION] No critical signals to verify")
        return beliefs

    total_searches = 0

    for belief in critical_beliefs:
        if total_searches >= max_total_searches:
            break

        signal = belief.get("signal", "").upper()
        queries = _VERIFICATION_QUERIES.get(signal, [])
        if not queries:
            continue

        secondary_sources: List[Dict[str, str]] = []
        authoritative_count = 0
        wire_count = 0

        for query_template in queries[:MAX_SEARCHES_PER_SIGNAL]:
            if total_searches >= max_total_searches:
                break

            query = query_template.format(country=country_name)
            total_searches += 1

            try:
                results = web_search(query, max_results=3)
            except Exception as e:
                logger.debug("[CORROBORATION] Search failed: %s", e)
                continue

            for result in results:
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                url = result.get("url", "")
                combined = f"{title} {snippet} {url}"

                source_class = _classify_source(combined)
                if source_class:
                    secondary_sources.append({
                        "title": title[:100],
                        "url": url,
                        "source_class": source_class,
                    })
                    if source_class == "official":
                        authoritative_count += 1
                    elif source_class == "wire":
                        wire_count += 1

        # ── Update verification status ───────────────────────────
        n_secondary = len(secondary_sources)
        existing_status = belief.get("verification_status", "unverified")

        if authoritative_count >= 1 and (wire_count >= 1 or n_secondary >= 3):
            new_status = "confirmed"
        elif n_secondary >= 2:
            new_status = "corroborated"
        elif n_secondary >= 1:
            new_status = "partially-corroborated"
        else:
            new_status = existing_status  # keep what accumulator set

        # Only upgrade, never downgrade
        _status_rank = {
            "unverified": 0, "single-source": 1,
            "partially-corroborated": 2, "corroborated": 3, "confirmed": 4,
        }
        if _status_rank.get(new_status, 0) > _status_rank.get(existing_status, 0):
            belief["verification_status"] = new_status

        belief["secondary_sources"] = secondary_sources
        belief["corroboration_detail"] = {
            "secondary_search_count": total_searches,
            "authoritative_hits": authoritative_count,
            "wire_hits": wire_count,
            "total_secondary_sources": n_secondary,
        }

        if n_secondary > 0:
            logger.info(
                "[CORROBORATION] %s: %d secondary sources found "
                "(official=%d, wire=%d) → %s",
                signal, n_secondary, authoritative_count, wire_count,
                belief["verification_status"],
            )

    return beliefs


# =====================================================================
# Helpers
# =====================================================================

def _classify_source(text: str) -> str:
    """Classify a search result as official/wire/quality or empty."""
    for source_class, pattern in _AUTHORITATIVE_PATTERNS.items():
        if pattern.search(text):
            return source_class
    return ""


# ISO-3 → country name fallback
_ISO_NAME_MAP: Dict[str, str] = {
    "IRN": "Iran", "USA": "United States", "CHN": "China",
    "RUS": "Russia", "IND": "India", "PAK": "Pakistan",
    "PRK": "North Korea", "KOR": "South Korea", "ISR": "Israel",
    "UKR": "Ukraine", "SAU": "Saudi Arabia", "TUR": "Turkey",
    "TWN": "Taiwan", "GBR": "United Kingdom", "FRA": "France",
    "DEU": "Germany", "JPN": "Japan",
}


def _iso_to_name(iso: str) -> str:
    return _ISO_NAME_MAP.get(iso.strip().upper(), iso)


__all__ = [
    "verify_critical_claims",
    "CRITICAL_SIGNALS",
]
