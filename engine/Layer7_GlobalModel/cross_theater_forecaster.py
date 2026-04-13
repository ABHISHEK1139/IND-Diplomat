"""
Phase 7.4 — Cross-Theater Forecast Adjustment
================================================

Adjusts a theater's P(HIGH 14d) probability based on contagion
from neighboring theaters.

Also provides:
    - Global risk summary (aggregate risk across all theaters)
    - Global Black Swan detection (systemic cascade)
    - Theater centrality (strategic importance based on coupling)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from engine.Layer7_GlobalModel.global_state import (
    GLOBAL_THEATERS,
    get_all_theaters,
    get_active_theaters,
    TheaterState,
)
from engine.Layer7_GlobalModel.interdependence_matrix import (
    get_incoming,
    get_weight,
    get_neighbors,
)

logger = logging.getLogger("Layer7_GlobalModel.cross_theater_forecaster")

# ── Configuration ────────────────────────────────────────────────
SPILLOVER_FACTOR = 0.20          # How much neighbor prob affects target
SYSTEMIC_CASCADE_THRESHOLD = 4.0 # Sum of all SRE > this = systemic shock


def adjusted_probability(country: str) -> Dict[str, float]:
    """Compute spillover-adjusted P(HIGH 14d) for a theater.

    Formula:
        adjusted = base_prob + Σ(neighbor.prob_high × weight × SPILLOVER_FACTOR)

    Returns
    -------
    dict
        {
            "base_prob": float,
            "spillover": float,
            "adjusted_prob": float,
            "contributors": list,  # [(source, prob, weight, contribution)]
        }
    """
    cc = country.upper()
    theater = GLOBAL_THEATERS.get(cc)
    if theater is None:
        return {
            "base_prob": 0.0,
            "spillover": 0.0,
            "adjusted_prob": 0.0,
            "contributors": [],
        }

    base = theater.prob_high_14d
    incoming = get_incoming(cc)

    spillover = 0.0
    contributors = []

    for source_cc, weight in incoming:
        source = GLOBAL_THEATERS.get(source_cc)
        if source is None or source.prob_high_14d < 0.01:
            continue

        contribution = round(source.prob_high_14d * weight * SPILLOVER_FACTOR, 6)
        if contribution > 0.001:
            spillover += contribution
            contributors.append({
                "source": source_cc,
                "source_prob": round(source.prob_high_14d, 4),
                "weight": round(weight, 4),
                "contribution": round(contribution, 4),
            })

    spillover = round(spillover, 6)
    adjusted = round(min(1.0, base + spillover), 4)

    if spillover > 0.001:
        logger.info(
            "[FORECAST] %s: base=%.1f%% + spillover=%.1f%% = adjusted=%.1f%% (%d contributors)",
            cc, base * 100, spillover * 100, adjusted * 100, len(contributors),
        )

    return {
        "base_prob": round(base, 4),
        "spillover": spillover,
        "adjusted_prob": adjusted,
        "contributors": contributors,
    }


def global_risk_summary() -> Dict[str, any]:
    """Aggregate risk assessment across all active theaters.

    Returns
    -------
    dict
        {
            "total_sre": float,
            "avg_sre": float,
            "max_sre": float,
            "max_theater": str,
            "active_count": int,
            "total_theaters": int,
            "systemic_risk": bool,
            "theaters": [{"country": str, "sre": float, "prob_high": float}],
        }
    """
    all_theaters = get_all_theaters()
    active = get_active_theaters(sre_threshold=0.01)

    if not active:
        return {
            "total_sre": 0.0,
            "avg_sre": 0.0,
            "max_sre": 0.0,
            "max_theater": "NONE",
            "active_count": 0,
            "total_theaters": len(all_theaters),
            "systemic_risk": False,
            "theaters": [],
        }

    total = sum(t.current_sre for t in active.values())
    avg = total / len(active) if active else 0.0
    max_theater = max(active.items(), key=lambda x: x[1].current_sre)

    theater_list = sorted(
        [
            {
                "country": cc,
                "sre": round(t.current_sre, 4),
                "prob_high": round(t.prob_high_14d, 4),
                "contagion_received": round(t.contagion_received, 4),
                "expansion_mode": t.expansion_mode,
            }
            for cc, t in active.items()
        ],
        key=lambda x: -x["sre"],
    )

    systemic = total > SYSTEMIC_CASCADE_THRESHOLD

    if systemic:
        logger.warning(
            "[GLOBAL] SYSTEMIC CASCADE: total_sre=%.2f > %.2f threshold",
            total, SYSTEMIC_CASCADE_THRESHOLD,
        )

    return {
        "total_sre": round(total, 4),
        "avg_sre": round(avg, 4),
        "max_sre": round(max_theater[1].current_sre, 4),
        "max_theater": max_theater[0],
        "active_count": len(active),
        "total_theaters": len(all_theaters),
        "systemic_risk": systemic,
        "theaters": theater_list,
    }


def global_black_swan() -> bool:
    """Detect systemic cascade (world-crisis-level event).

    Returns True if the sum of all theater SRE scores exceeds
    SYSTEMIC_CASCADE_THRESHOLD (default 4.0).

    This means multiple theaters are simultaneously at HIGH or
    CRITICAL — indicating a potential global conflict cascade.
    """
    total = sum(t.current_sre for t in GLOBAL_THEATERS.values())
    triggered = total > SYSTEMIC_CASCADE_THRESHOLD
    if triggered:
        logger.warning(
            "[GLOBAL_BLACKSWAN] SYSTEMIC CASCADE DETECTED: total_sre=%.2f",
            total,
        )
    return triggered


def theater_centrality(country: str) -> float:
    """Compute strategic centrality of a theater.

    Centrality = sum of all coupling weights (incoming + outgoing).
    Higher centrality = theater whose escalation has more global impact.
    """
    cc = country.upper()
    outgoing = sum(w for _, w in get_neighbors(cc))
    incoming = sum(w for _, w in get_incoming(cc))
    return round(outgoing + incoming, 4)


def prioritized_collection_targets() -> List[Tuple[str, float]]:
    """Rank theaters by collection priority.

    Priority = current_risk × centrality × uncertainty

    Where:
        risk = SRE
        centrality = theater_centrality()
        uncertainty = 1.0 - prob_high (higher when outcome uncertain)

    Returns list of (country, priority_score) sorted descending.
    """
    targets = []
    for cc, t in GLOBAL_THEATERS.items():
        risk = t.current_sre
        centrality = theater_centrality(cc)
        uncertainty = 1.0 - abs(2 * t.prob_high_14d - 1)  # max at 0.5
        priority = round(risk * centrality * uncertainty, 4)
        if priority > 0.001:
            targets.append((cc, priority))

    return sorted(targets, key=lambda x: -x[1])
