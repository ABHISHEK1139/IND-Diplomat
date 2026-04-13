"""
Signal Normalizer — Pre-processing layer for signal deduplication.

Sits BETWEEN signal extraction and the belief accumulator.
Does NOT modify either system.

Usage::

    from Core.signals.signal_normalizer import normalize_signal

    raw = "SIG_SANCTIONS_ACTIVE"
    canonical = normalize_signal(raw)  # → "SIG_ECONOMIC_PRESSURE"
"""

from __future__ import annotations

from typing import Dict, List, Set


# ── Canonical mapping — all known variants → single form ─────────
# This extends the existing signal_registry's ALIAS_TO_CANONICAL
# with additional legacy/variant tokens encountered in the wild.

CANONICAL_SIGNAL_MAP: Dict[str, str] = {
    # ── Economic variants ─────────────────────────────────────────
    "SIG_SANCTIONS_ACTIVE":         "SIG_ECONOMIC_PRESSURE",
    "SIG_ECO_SANCTIONS_ACTIVE":     "SIG_ECONOMIC_PRESSURE",
    "SIG_ECO_PRESSURE_HIGH":        "SIG_ECONOMIC_PRESSURE",
    "SIG_ECON_PRESSURE":            "SIG_ECONOMIC_PRESSURE",
    "SIG_ECO_TRADE_LEVERAGE":       "SIG_ECONOMIC_PRESSURE",
    "SIG_TRADE_EMBARGO":            "SIG_ECONOMIC_PRESSURE",
    "SIG_FINANCIAL_STRESS":         "SIG_ECONOMIC_PRESSURE",
    "SIG_SUPPLY_CHAIN_DISRUPTION":  "SIG_ECONOMIC_PRESSURE",

    # ── Stability variants ────────────────────────────────────────
    "SIG_DOM_INTERNAL_INSTABILITY": "SIG_INTERNAL_INSTABILITY",
    "SIG_DOM_CIVIL_UNREST":         "SIG_INTERNAL_INSTABILITY",
    "SIG_DOM_REGIME_INSTABILITY":   "SIG_INTERNAL_INSTABILITY",
    "SIG_DOM_PROTEST_PRESSURE":     "SIG_PUBLIC_PROTEST",
    "SIG_CIVIL_UNREST":             "SIG_INTERNAL_INSTABILITY",
    "SIG_REGIME_COLLAPSE":          "SIG_INTERNAL_INSTABILITY",

    # ── Military variants ─────────────────────────────────────────
    "SIG_MIL_FORWARD_DEPLOYMENT":   "SIG_FORCE_POSTURE",
    "SIG_FORCE_CONCENTRATION":      "SIG_FORCE_POSTURE",
    "SIG_MIL_EXERCISE_ESCALATION":  "SIG_FORCE_POSTURE",
    "SIG_EXERCISE_ESCALATION":      "SIG_FORCE_POSTURE",
    "SIG_LOGISTICS_SURGE":          "SIG_LOGISTICS_PREP",
    "SIG_MIL_LOGISTICS_SURGE":      "SIG_LOGISTICS_PREP",
    "SIG_MIL_BORDER_CLASHES":       "SIG_MIL_ESCALATION",
    "SIG_CYBER_PREPARATION":        "SIG_CYBER_ACTIVITY",
    "SIG_CAP_CYBER_PREPARATION":    "SIG_CYBER_ACTIVITY",
    "SIG_CAP_SUPPLY_STOCKPILING":   "SIG_LOGISTICS_PREP",
    "SIG_CAP_EVACUATION_ACTIVITY":  "SIG_INTERNAL_INSTABILITY",

    # ── Diplomatic variants ───────────────────────────────────────
    "SIG_DIP_HOSTILE_RHETORIC":     "SIG_DIP_HOSTILITY",
    "SIG_ALLIANCE_SHIFT":           "SIG_ALLIANCE_ACTIVATION",
    "SIG_DIP_CHANNEL_CLOSURE":      "SIG_NEGOTIATION_BREAKDOWN",
    "SIG_DIP_ALLIANCE_COORDINATION":"SIG_ALLIANCE_ACTIVATION",
    "SIG_COERCIVE_PRESSURE":        "SIG_COERCIVE_BARGAINING",
    "SIG_RETALIATORY_THREAT":       "SIG_COERCIVE_BARGAINING",
    "SIG_DIP_DEESCALATION":         "SIG_DIPLOMACY_ACTIVE",
    "SIG_DIP_CHANNEL_OPEN":         "SIG_DIPLOMACY_ACTIVE",
    "SIG_REGIME_STABLE":            "SIG_DIPLOMACY_ACTIVE",
}


def normalize_signal(signal: str) -> str:
    """
    Normalize a signal token to its canonical form.

    Apply this right after signal extraction and BEFORE
    the belief accumulator.

    Parameters
    ----------
    signal : str
        Raw signal token from any source.

    Returns
    -------
    str
        Canonical signal token.

    Examples
    --------
    >>> normalize_signal("SIG_SANCTIONS_ACTIVE")
    'SIG_ECONOMIC_PRESSURE'
    >>> normalize_signal("SIG_MIL_MOBILIZATION")
    'SIG_MIL_MOBILIZATION'
    """
    signal = str(signal or "").strip().upper()
    return CANONICAL_SIGNAL_MAP.get(signal, signal)


def normalize_batch(signals: List[str]) -> List[str]:
    """
    Normalize and deduplicate a batch of signals.

    Returns unique canonical tokens in encountered order.
    """
    seen: Set[str] = set()
    result: List[str] = []
    for s in signals:
        canonical = normalize_signal(s)
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result
