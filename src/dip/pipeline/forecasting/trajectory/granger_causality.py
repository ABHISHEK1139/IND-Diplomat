"""
Granger Causality — Statistical Causal Chain Detection
=======================================================

Uses statsmodels Granger causality to detect which signals predict others.
Example: "Does troop_movement Granger-cause diplomatic_recall?"

Port of DIP_8 concept with statsmodels backend.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import numpy as np

logger = logging.getLogger("Layer5_Trajectory.granger")

try:
    from statsmodels.tsa.stattools import grangercausalitytests
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False


def find_causal_chains(
    signal_series: Dict[str, List[float]],
    max_lag: int = 5,
    significance: float = 0.05,
) -> List[Dict[str, Any]]:
    """Find Granger-causal relationships between signal time series.

    Args:
        signal_series: {signal_name: [values over time]}
        max_lag: Maximum lag to test
        significance: p-value threshold for significance

    Returns:
        [{cause, effect, lag, p_value, significant}]
    """
    if not STATSMODELS_AVAILABLE:
        return _correlation_fallback(signal_series)

    results = []
    names = list(signal_series.keys())

    for cause_name in names:
        for effect_name in names:
            if cause_name == effect_name:
                continue

            cause = np.array(signal_series[cause_name])
            effect = np.array(signal_series[effect_name])

            if len(cause) < max_lag + 5:
                continue

            try:
                data = np.column_stack([effect, cause])
                gc_result = grangercausalitytests(data, max_lag, verbose=False)

                best_p = 1.0
                best_lag = 1
                for lag, test_result in gc_result.items():
                    p_value = test_result[0]["ssr_ftest"][1]
                    if p_value < best_p:
                        best_p = p_value
                        best_lag = lag

                results.append({
                    "cause": cause_name,
                    "effect": effect_name,
                    "lag": best_lag,
                    "p_value": round(best_p, 4),
                    "significant": best_p < significance,
                })
            except Exception:
                continue

    # Sort by most significant
    results.sort(key=lambda r: r["p_value"])
    return results[:20]


def _correlation_fallback(signal_series: Dict[str, List[float]]) -> List[Dict[str, Any]]:
    """Simple cross-correlation fallback when statsmodels unavailable."""
    results = []
    names = list(signal_series.keys())

    for cause_name in names:
        for effect_name in names:
            if cause_name == effect_name:
                continue
            cause = np.array(signal_series[cause_name])
            effect = np.array(signal_series[effect_name])
            min_len = min(len(cause), len(effect))
            if min_len < 3:
                continue

            correlation = np.corrcoef(cause[:min_len], effect[:min_len])[0, 1]
            if abs(correlation) > 0.5:
                results.append({
                    "cause": cause_name,
                    "effect": effect_name,
                    "lag": 1,
                    "p_value": round(1.0 - abs(correlation), 4),
                    "significant": abs(correlation) > 0.7,
                    "method": "correlation_fallback",
                })

    results.sort(key=lambda r: r["p_value"])
    return results[:20]
