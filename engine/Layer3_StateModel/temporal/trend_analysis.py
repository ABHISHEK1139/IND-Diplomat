"""
Temporal trend computation from rolling Layer-3 state history.

Fix 5: Replaced naive endpoint delta with weighted linear regression.
- Lowered MIN_TREND_POINTS from 5 to 2 (graceful degradation).
- Exponential recency weighting so recent runs count more.
- 2 points = simple delta, 3+ = weighted least-squares regression.
- Added accelerating_pattern flag for early warning.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

from engine.Layer3_StateModel.temporal.state_history import load_state_history

logger = logging.getLogger("Layer3.trend_analysis")

# Fix 5: Lowered from 5 → 2 so trends activate after just 2 runs
MIN_TREND_POINTS = 2
_DECAY = 0.80  # exponential weight decay — recent runs count more


def _weighted_slope(rows: List[Dict[str, Any]], key: str) -> float:
    """
    Compute weighted linear regression slope.

    - 2 points: simple delta (end - start)
    - 3+ points: least-squares with exponential recency weighting

    Returns slope per run (positive = increasing, negative = decreasing).
    """
    n = len(rows)
    if n < 2:
        return 0.0

    values = [float(row.get(key, 0.0) or 0.0) for row in rows]

    if n == 2:
        return values[1] - values[0]

    # Weighted least-squares regression: y = a + b*x
    # Weight each point: w_i = decay^(n-1-i) — most recent gets w=1.0
    sum_w = 0.0
    sum_wx = 0.0
    sum_wy = 0.0
    sum_wxx = 0.0
    sum_wxy = 0.0

    for i in range(n):
        w = _DECAY ** (n - 1 - i)  # most recent = highest weight
        x = float(i)
        y = values[i]
        sum_w += w
        sum_wx += w * x
        sum_wy += w * y
        sum_wxx += w * x * x
        sum_wxy += w * x * y

    denom = sum_w * sum_wxx - sum_wx * sum_wx
    if abs(denom) < 1e-12:
        return 0.0

    slope = (sum_w * sum_wxy - sum_wx * sum_wy) / denom
    return slope


def compute_trend(country_code: str) -> Dict[str, float]:
    """
    Compute temporal trends from state history using weighted regression.

    Returns trend slopes for capability, intent, stability, conflict.
    Also detects accelerating patterns (both capability AND intent
    trending up simultaneously).
    """
    history = load_state_history(country_code)
    if len(history) < MIN_TREND_POINTS:
        logger.debug(
            "[TREND] %s: only %d history point(s) (need %d) — returning empty",
            country_code, len(history), MIN_TREND_POINTS,
        )
        return {}

    cap_trend = _weighted_slope(history, "capability")
    int_trend = _weighted_slope(history, "intent")
    stab_trend = _weighted_slope(history, "stability")
    conf_trend = _weighted_slope(history, "conflict")

    # Detect accelerating escalation pattern
    accelerating = (cap_trend > 0.02 and int_trend > 0.02)

    result = {
        "capability_trend": round(cap_trend, 6),
        "intent_trend": round(int_trend, 6),
        "stability_trend": round(stab_trend, 6),
        "conflict_trend": round(conf_trend, 6),
        "accelerating_pattern": accelerating,
    }

    logger.info(
        "[TREND] %s: cap=%+.4f int=%+.4f stab=%+.4f conf=%+.4f accel=%s (%d pts)",
        country_code, cap_trend, int_trend, stab_trend, conf_trend,
        accelerating, len(history),
    )

    return result


__all__ = ["compute_trend"]
