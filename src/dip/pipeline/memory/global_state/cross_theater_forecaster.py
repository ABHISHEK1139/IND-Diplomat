"""
Cross-Theater Forecaster — Multi-Theater Contagion Analysis
=============================================================

Models how escalation in one theater propagates to others.
Uses NetworkX graph-based contagion with temporal weighting.

Port of DIP_8 engine/Layer7_GlobalModel/cross_theater_forecaster.py
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Layer7_Global.cross_theater")

try:
    import networkx as nx
    NETWORKX = True
except ImportError:
    NETWORKX = False


# Theater adjacency matrix (how much theater A affects theater B)
THEATER_ADJACENCY: Dict[str, Dict[str, float]] = {
    "indo_pacific": {"south_asia": 0.7, "middle_east": 0.3, "europe": 0.1},
    "south_asia": {"indo_pacific": 0.6, "middle_east": 0.4, "europe": 0.1},
    "middle_east": {"south_asia": 0.4, "indo_pacific": 0.2, "europe": 0.5},
    "europe": {"middle_east": 0.3, "indo_pacific": 0.2, "south_asia": 0.1},
}

# Country → Theater mapping
COUNTRY_THEATER: Dict[str, str] = {
    "IND": "south_asia", "CHN": "indo_pacific", "PAK": "south_asia",
    "USA": "europe", "RUS": "europe", "JPN": "indo_pacific",
    "AUS": "indo_pacific", "KOR": "indo_pacific", "TWN": "indo_pacific",
    "ISR": "middle_east", "IRN": "middle_east", "SAU": "middle_east",
    "TUR": "middle_east", "GBR": "europe", "FRA": "europe", "DEU": "europe",
}


def forecast_cross_theater(
    source_country: str,
    sre_score: float,
    country_scores: Optional[Dict[str, float]] = None,
    decay_factor: float = 0.5,
    max_hops: int = 2,
) -> Dict[str, Any]:
    """Forecast contagion from source country to connected theaters.

    Args:
        source_country: Country where escalation originates
        sre_score: SRE escalation score [0-1]  
        country_scores: Existing SRE scores for other countries
        decay_factor: How much contagion decays per hop
        max_hops: Maximum propagation hops

    Returns:
        {theater_scores, country_spillover, recommendations}
    """
    source_theater = COUNTRY_THEATER.get(source_country.upper(), "unknown")
    
    if source_theater not in THEATER_ADJACENCY:
        return {
            "source_theater": source_theater,
            "theater_scores": {},
            "country_spillover": {},
            "recommendations": ["Unknown theater — cannot forecast cross-theater effects."],
        }

    # Initialize theater scores
    theater_scores: Dict[str, float] = {source_theater: sre_score}
    unvisited = set(THEATER_ADJACENCY.keys())
    unvisited.discard(source_theater)

    for hop in range(max_hops):
        next_scores: Dict[str, float] = {}
        for theater, score in list(theater_scores.items()):
            if theater not in THEATER_ADJACENCY:
                continue
            for neighbor, weight in THEATER_ADJACENCY[theater].items():
                if neighbor in unvisited:
                    spillover = score * weight * (decay_factor ** (hop + 1))
                    next_scores[neighbor] = max(
                        next_scores.get(neighbor, 0), spillover
                    )

        for theater, score in next_scores.items():
            if score > 0.05:  # threshold
                theater_scores[theater] = score
                unvisited.discard(theater)

        if not unvisited:
            break

    # Country-level spillover
    country_spillover: Dict[str, float] = {}
    if country_scores:
        for country, base_score in country_scores.items():
            theater = COUNTRY_THEATER.get(country, "")
            base = country_spillover.get(country, base_score)
            if theater in theater_scores:
                country_spillover[country] = max(base, theater_scores[theater] * 0.8)

    # Recommendations
    recs = []
    high_contagion = [t for t, s in theater_scores.items() if s > 0.5]
    if high_contagion:
        recs.append(f"High contagion risk in: {', '.join(high_contagion)} — prepare theater-level contingencies.")
    if len(theater_scores) > 2:
        recs.append("Multi-theater escalation pattern detected — escalate to strategic command.")

    return {
        "source_theater": source_theater,
        "source_country": source_country,
        "theater_scores": {k: round(v, 4) for k, v in theater_scores.items()},
        "country_spillover": {k: round(v, 4) for k, v in sorted(country_spillover.items(), key=lambda x: x[1], reverse=True)[:10]},
        "contagion_depth": len(theater_scores) - 1,
        "recommendations": recs,
    }
