"""
Escalation synchronization index (ESI).

Detects coordinated rises across multiple escalation-relevant dimensions.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

_RISING_THRESHOLD = 0.05
_SYNC_RATIO_THRESHOLD = 0.75


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _dimension_delta(prev: Dict[str, Any], curr: Dict[str, Any], key: str) -> float:
    return _safe_float(curr.get(key, 0.0), 0.0) - _safe_float(prev.get(key, 0.0), 0.0)


def compute_esi(history: Iterable[Dict[str, Any]]) -> float:
    """
    Computes Escalation Synchronization Index in [0, 1].

    History rows are expected to contain:
      - capability
      - intent
      - stability
      - conflict
    """
    rows: List[Dict[str, Any]] = [row for row in list(history or []) if isinstance(row, dict)]
    if len(rows) < 3:
        return 0.0

    sync_events = 0
    transitions = 0

    for idx in range(1, len(rows)):
        prev = rows[idx - 1]
        curr = rows[idx]

        rises = []
        # Core war-preparation dimensions
        rises.append(_dimension_delta(prev, curr, "capability") > _RISING_THRESHOLD)
        rises.append(_dimension_delta(prev, curr, "intent") > _RISING_THRESHOLD)
        rises.append(_dimension_delta(prev, curr, "conflict") > _RISING_THRESHOLD)
        # Instability rises when stability declines.
        rises.append(_dimension_delta(prev, curr, "stability") < -_RISING_THRESHOLD)

        transitions += 1
        if (sum(1 for flag in rises if flag) / float(len(rises))) >= _SYNC_RATIO_THRESHOLD:
            sync_events += 1

    if transitions <= 0:
        return 0.0

    return round(max(0.0, min(1.0, sync_events / float(transitions))), 3)


__all__ = ["compute_esi"]

