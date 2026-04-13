"""
Unified Signal Registry — Single Source of Truth
=================================================
All modules import canonical signal definitions from here.
Eliminates the 5+ duplicate signal vocabularies that previously
inflated domain scores (e.g. 5 economic signals → cost_raw=0.96).

Design
------
- **CANONICAL_TOKENS**: ~20 canonical signal concepts.
- **ALIAS_TO_CANONICAL**: every known variant → its canonical form.
- **SIGNAL_DIMENSION**: canonical token → SRE dimension.
- **SIGNAL_TO_GROUP**: canonical token → Bayesian profile group.
- **canonicalize(token)**: single function all modules call.
- **DIMENSION_FLOORS**: minimum confidence per dimension
  (prevents multiplicative suppression from crushing signals to zero).

Author: IND-DIPLOMAT system  |  Phase: Calibration (v1)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Set

logger = logging.getLogger("Layer3.signal_registry")


# ══════════════════════════════════════════════════════════════════════
#  1.  CANONICAL SIGNAL TOKENS — one per analytical concept
# ══════════════════════════════════════════════════════════════════════

CANONICAL_TOKENS: List[str] = [
    # ── CAPABILITY ──
    "SIG_MIL_MOBILIZATION",     # troop staging / mobilization
    "SIG_MIL_ESCALATION",       # kinetic activity / border clashes
    "SIG_FORCE_POSTURE",        # force concentration / forward deployment
    "SIG_LOGISTICS_PREP",       # logistics surge / supply movement
    "SIG_CYBER_ACTIVITY",       # cyber preparation / intrusions
    # ── INTENT ──
    "SIG_DIP_HOSTILITY",        # hostile rhetoric / diplomatic threats
    "SIG_DIPLOMACY_ACTIVE",     # open channels / de-escalation signals
    "SIG_COERCIVE_BARGAINING",  # coercive pressure / retaliatory threats
    "SIG_ALLIANCE_ACTIVATION",  # alliance coordination / shift
    "SIG_NEGOTIATION_BREAKDOWN",# channel closure / talks suspended
    "SIG_DETERRENCE_SIGNALING", # deterrence posture / signaling
    # ── STABILITY ──
    "SIG_INTERNAL_INSTABILITY", # domestic unrest / regime instability
    "SIG_PUBLIC_PROTEST",       # protest pressure / civil unrest
    "SIG_DECEPTION_ACTIVITY",   # deception / concealment activity
    "SIG_ELITE_FRACTURE",       # leadership fractures / governance stress
    "SIG_MILITARY_DEFECTION",   # military defection / command breakdown
    # ── COST ──
    "SIG_ECONOMIC_PRESSURE",    # sanctions / economic coercion / trade leverage
    # ── COMPOSITE ──
    "SIG_KINETIC_ACTIVITY",     # confirmed strikes / casualties
    "SIG_WMD_RISK",             # WMD / nuclear / CBRN indicators
]

CANONICAL_TOKEN_SET: Set[str] = set(CANONICAL_TOKENS)


# ══════════════════════════════════════════════════════════════════════
#  2.  ALIAS → CANONICAL mapping  (all known variants)
# ══════════════════════════════════════════════════════════════════════

ALIAS_TO_CANONICAL: Dict[str, str] = {
    # ── Economic duplicates (the ROOT CAUSE of cost_raw inflation) ──
    "SIG_SANCTIONS_ACTIVE":       "SIG_ECONOMIC_PRESSURE",
    "SIG_ECO_SANCTIONS_ACTIVE":   "SIG_ECONOMIC_PRESSURE",
    "SIG_ECON_PRESSURE":          "SIG_ECONOMIC_PRESSURE",
    "SIG_ECO_PRESSURE_HIGH":      "SIG_ECONOMIC_PRESSURE",

    # ── Military aliases ──
    "SIG_MIL_FORWARD_DEPLOYMENT": "SIG_FORCE_POSTURE",
    "SIG_MIL_EXERCISE_ESCALATION":"SIG_FORCE_POSTURE",
    "SIG_FORCE_CONCENTRATION":    "SIG_FORCE_POSTURE",
    "SIG_MIL_BORDER_CLASHES":     "SIG_MIL_ESCALATION",
    "SIG_LOGISTICS_SURGE":        "SIG_LOGISTICS_PREP",
    "SIG_MIL_LOGISTICS_SURGE":    "SIG_LOGISTICS_PREP",
    "SIG_CYBER_PREPARATION":      "SIG_CYBER_ACTIVITY",
    "SIG_CAP_CYBER_PREPARATION":  "SIG_CYBER_ACTIVITY",
    "SIG_EXERCISE_ESCALATION":    "SIG_FORCE_POSTURE",

    # ── Diplomatic aliases ──
    "SIG_DIP_HOSTILE_RHETORIC":   "SIG_DIP_HOSTILITY",
    "SIG_ALLIANCE_SHIFT":         "SIG_ALLIANCE_ACTIVATION",
    "SIG_DIP_CHANNEL_CLOSURE":    "SIG_NEGOTIATION_BREAKDOWN",
    "SIG_DIP_ALLIANCE_COORDINATION": "SIG_ALLIANCE_ACTIVATION",
    "SIG_COERCIVE_PRESSURE":      "SIG_COERCIVE_BARGAINING",
    "SIG_RETALIATORY_THREAT":     "SIG_COERCIVE_BARGAINING",

    # ── Stability aliases ──
    "SIG_DOM_INTERNAL_INSTABILITY": "SIG_INTERNAL_INSTABILITY",
    "SIG_DOM_CIVIL_UNREST":       "SIG_INTERNAL_INSTABILITY",
    "SIG_DOM_REGIME_INSTABILITY": "SIG_INTERNAL_INSTABILITY",
    "SIG_DOM_PROTEST_PRESSURE":   "SIG_PUBLIC_PROTEST",

    # ── Prefixed canonical duplicates ──
    "SIG_MIL_MOBILIZATION":      "SIG_MIL_MOBILIZATION",   # identity
    "SIG_ECO_TRADE_LEVERAGE":    "SIG_ECONOMIC_PRESSURE",
    "SIG_CAP_SUPPLY_STOCKPILING":"SIG_LOGISTICS_PREP",
    "SIG_CAP_EVACUATION_ACTIVITY":"SIG_INTERNAL_INSTABILITY",
    "SIG_DIP_DEESCALATION":      "SIG_DIPLOMACY_ACTIVE",
    "SIG_DIP_CHANNEL_OPEN":      "SIG_DIPLOMACY_ACTIVE",
    "SIG_REGIME_STABLE":         "SIG_DIPLOMACY_ACTIVE",    # de-escalatory signal
}


# ══════════════════════════════════════════════════════════════════════
#  3.  CANONICAL TOKEN → SRE DIMENSION
# ══════════════════════════════════════════════════════════════════════

SIGNAL_DIMENSION: Dict[str, str] = {
    # CAPABILITY
    "SIG_MIL_MOBILIZATION":      "CAPABILITY",
    "SIG_MIL_ESCALATION":        "CAPABILITY",
    "SIG_FORCE_POSTURE":         "CAPABILITY",
    "SIG_LOGISTICS_PREP":        "CAPABILITY",
    "SIG_CYBER_ACTIVITY":        "CAPABILITY",
    "SIG_KINETIC_ACTIVITY":      "CAPABILITY",
    # INTENT
    "SIG_DIP_HOSTILITY":         "INTENT",
    "SIG_DIPLOMACY_ACTIVE":      "INTENT",
    "SIG_COERCIVE_BARGAINING":   "INTENT",
    "SIG_ALLIANCE_ACTIVATION":   "INTENT",
    "SIG_NEGOTIATION_BREAKDOWN": "INTENT",
    "SIG_DETERRENCE_SIGNALING":  "INTENT",
    # STABILITY
    "SIG_INTERNAL_INSTABILITY":  "STABILITY",
    "SIG_PUBLIC_PROTEST":        "STABILITY",
    "SIG_DECEPTION_ACTIVITY":    "STABILITY",
    "SIG_ELITE_FRACTURE":        "STABILITY",
    "SIG_MILITARY_DEFECTION":    "STABILITY",
    # COST
    "SIG_ECONOMIC_PRESSURE":     "COST",
    # COMPOSITE
    "SIG_WMD_RISK":              "CAPABILITY",
}


# ══════════════════════════════════════════════════════════════════════
#  4.  CANONICAL TOKEN → BAYESIAN PROFILE GROUP
# ══════════════════════════════════════════════════════════════════════

SIGNAL_TO_GROUP: Dict[str, str] = {
    "SIG_MIL_ESCALATION":        "mil_escalation",
    "SIG_MIL_MOBILIZATION":      "mobilization",
    "SIG_FORCE_POSTURE":         "force_posture",
    "SIG_LOGISTICS_PREP":        "logistics",
    "SIG_DIP_HOSTILITY":         "hostility",
    "SIG_COERCIVE_BARGAINING":   "coercive",
    "SIG_DIPLOMACY_ACTIVE":      "diplomacy_active",
    "SIG_DETERRENCE_SIGNALING":  "coercive",
    "SIG_ALLIANCE_ACTIVATION":   "alliance",
    "SIG_NEGOTIATION_BREAKDOWN": "hostility",
    "SIG_WMD_RISK":              "wmd_risk",
    "SIG_INTERNAL_INSTABILITY":  "instability",
    "SIG_PUBLIC_PROTEST":        "instability",
    "SIG_ELITE_FRACTURE":        "instability",
    "SIG_MILITARY_DEFECTION":    "instability",
    "SIG_DECEPTION_ACTIVITY":    "coercive",
    "SIG_ECONOMIC_PRESSURE":     "economic_pressure",
    "SIG_CYBER_ACTIVITY":        "cyber",
    "SIG_KINETIC_ACTIVITY":      "mil_escalation",
}


# ══════════════════════════════════════════════════════════════════════
#  5.  DIMENSION CONFIDENCE FLOORS
# ══════════════════════════════════════════════════════════════════════
# Prevents multiplicative suppression from crushing signals below
# analytically meaningful thresholds.  Military signals with even
# one credible source should never drop below 0.15.

DIMENSION_FLOORS: Dict[str, float] = {
    "CAPABILITY": 0.15,
    "INTENT":     0.12,
    "STABILITY":  0.12,
    "COST":       0.20,    # OSINT-rich, should have higher floor
    "UNKNOWN":    0.10,
}


# ══════════════════════════════════════════════════════════════════════
#  6.  CANONICALIZE — the single function all modules call
# ══════════════════════════════════════════════════════════════════════

def canonicalize(token: str) -> str:
    """
    Normalise any signal token to its canonical form.

    - Uppercases and strips whitespace
    - Maps known aliases to canonical tokens
    - Unknown tokens pass through unchanged (forward-compatible)

    Examples
    --------
    >>> canonicalize("SIG_SANCTIONS_ACTIVE")
    'SIG_ECONOMIC_PRESSURE'
    >>> canonicalize("SIG_DOM_INTERNAL_INSTABILITY")
    'SIG_INTERNAL_INSTABILITY'
    >>> canonicalize("SIG_MIL_MOBILIZATION")
    'SIG_MIL_MOBILIZATION'
    """
    token = str(token or "").strip().upper()
    if not token:
        return token
    return ALIAS_TO_CANONICAL.get(token, token)


def get_dimension(token: str) -> str:
    """Get SRE dimension for a signal token (canonicalises first)."""
    canonical = canonicalize(token)
    return SIGNAL_DIMENSION.get(canonical, "UNKNOWN")


def get_group(token: str) -> str:
    """Get Bayesian profile group for a signal token (canonicalises first)."""
    canonical = canonicalize(token)
    return SIGNAL_TO_GROUP.get(canonical, "")


def get_floor(token: str) -> float:
    """Get minimum confidence floor for a signal token."""
    dim = get_dimension(token)
    return DIMENSION_FLOORS.get(dim, 0.10)


__all__ = [
    "CANONICAL_TOKENS",
    "CANONICAL_TOKEN_SET",
    "ALIAS_TO_CANONICAL",
    "SIGNAL_DIMENSION",
    "SIGNAL_TO_GROUP",
    "DIMENSION_FLOORS",
    "canonicalize",
    "get_dimension",
    "get_group",
    "get_floor",
]
