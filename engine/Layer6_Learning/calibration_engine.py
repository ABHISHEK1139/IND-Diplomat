"""
Phase 6.3 — Self-Calibration Engine
=====================================

Aggregates Brier scores from resolved forecasts and interprets
the system's forecast quality.

Tiers
-----
  avg_brier < 0.15  →  EXCELLENT   (weights can trust trajectory)
  avg_brier < 0.25  →  ACCEPTABLE  (no adjustment needed)
  avg_brier ≥ 0.25  →  MISCALIBRATED  (auto-adjuster eligible)

Safety
------
  MIN_RESOLVED = 20  — system MUST accumulate ≥20 resolved forecasts
  before any auto-adjustment activates.  Prevents noise distortion.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from engine.Layer6_Learning.forecast_archive import load_history, count_resolved
from engine.Layer6_Learning.forecast_resolution import get_resolved_entries

logger = logging.getLogger("Layer6_Learning.calibration_engine")

# ── Minimum resolved forecasts before auto-adjustment ────────────
MIN_RESOLVED = 20

# ── Brier interpretation tiers ───────────────────────────────────
TIER_EXCELLENT     = 0.15
TIER_ACCEPTABLE    = 0.25
# anything >= TIER_ACCEPTABLE  →  MISCALIBRATED


def calibration_score(country: Optional[str] = None) -> Dict[str, any]:
    """Compute calibration score from resolved forecasts.

    Parameters
    ----------
    country : str or None
        If provided, compute for this country only.
        If None, compute globally across all countries.

    Returns
    -------
    dict
        {
            "avg_brier": float | None,
            "tier": str,          # EXCELLENT / ACCEPTABLE / MISCALIBRATED / INSUFFICIENT
            "n_resolved": int,
            "n_total": int,
            "min_required": int,  # MIN_RESOLVED
            "eligible": bool,     # n_resolved >= MIN_RESOLVED
            "by_country": dict,   # per-country breakdown (global only)
        }
    """
    resolved = get_resolved_entries(country)
    total = len(load_history(country))
    n_resolved = len(resolved)

    briers = [e.brier_score for e in resolved if e.brier_score is not None]
    avg = round(sum(briers) / len(briers), 6) if briers else None

    eligible = n_resolved >= MIN_RESOLVED
    tier = _interpret_tier(avg, eligible)

    result = {
        "avg_brier": avg,
        "tier": tier,
        "n_resolved": n_resolved,
        "n_total": total,
        "min_required": MIN_RESOLVED,
        "eligible": eligible,
    }

    # Per-country breakdown (only when computing globally)
    if country is None:
        by_country: Dict[str, dict] = {}
        all_entries = get_resolved_entries()
        countries = sorted({e.country for e in all_entries})
        for cc in countries:
            cc_entries = [e for e in all_entries if e.country == cc]
            cc_briers = [e.brier_score for e in cc_entries if e.brier_score is not None]
            cc_avg = round(sum(cc_briers) / len(cc_briers), 6) if cc_briers else None
            cc_eligible = len(cc_entries) >= MIN_RESOLVED
            by_country[cc] = {
                "avg_brier": cc_avg,
                "tier": _interpret_tier(cc_avg, cc_eligible),
                "n_resolved": len(cc_entries),
                "eligible": cc_eligible,
            }
        result["by_country"] = by_country

    logger.info(
        "[CALIBRATION] tier=%s  avg_brier=%s  resolved=%d/%d  eligible=%s",
        tier, avg, n_resolved, total, eligible,
    )
    return result


def calibration_report() -> str:
    """Human-readable calibration summary.

    Returns a multi-line string suitable for logs or reports.
    """
    score = calibration_score()
    lines = [
        f"Forecast Calibration: {score['tier']}",
        f"  Average Brier Score: {score['avg_brier'] if score['avg_brier'] is not None else 'N/A'}",
        f"  Resolved Forecasts:  {score['n_resolved']} / {score['n_total']}",
        f"  Minimum Required:    {score['min_required']}",
        f"  Auto-Adjust Eligible: {'YES' if score['eligible'] else 'NO'}",
    ]

    by_country = score.get("by_country", {})
    if by_country:
        lines.append("  Per-Country:")
        for cc, info in sorted(by_country.items()):
            b = info['avg_brier']
            lines.append(
                f"    {cc}: Brier={b if b is not None else 'N/A'}  "
                f"tier={info['tier']}  resolved={info['n_resolved']}"
            )

    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _interpret_tier(avg_brier: Optional[float], eligible: bool) -> str:
    if avg_brier is None or not eligible:
        return "INSUFFICIENT"
    if avg_brier < TIER_EXCELLENT:
        return "EXCELLENT"
    if avg_brier < TIER_ACCEPTABLE:
        return "ACCEPTABLE"
    return "MISCALIBRATED"
