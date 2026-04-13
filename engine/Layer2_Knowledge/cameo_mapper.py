"""
Minimal event-to-signal mapping bridge.

This module maps extracted event labels into Layer-3/Layer-4 signal tokens.
Supports both text labels and numeric CAMEO root codes.
"""

from __future__ import annotations

from typing import Iterable, List


# Text-label → signal mapping (existing system vocabulary)
CAMEO_SIGNAL_MAP = {
    "MOBILIZATION": "SIG_MIL_MOBILIZATION",
    "MIL_EXERCISE": "SIG_FORCE_POSTURE",
    "FORCE_POSTURE": "SIG_FORCE_POSTURE",
    "LOGISTICS": "SIG_LOGISTICS_PREP",
    "SANCTION": "SIG_SANCTIONS_ACTIVE",
    "TRADE_SHOCK": "SIG_ECON_PRESSURE",
    "HOSTILE_RHETORIC": "SIG_DIP_HOSTILE_RHETORIC",
    "NEGOTIATION_BREAKDOWN": "SIG_NEGOTIATION_BREAKDOWN",
    "CYBER_PREPARATION": "SIG_CYBER_PREPARATION",
    "PROTEST_SURGE": "SIG_INTERNAL_INSTABILITY",
}

# CAMEO root codes (01-20) → system signal tokens.
# This bridges raw GDELT event codes into the existing signal vocabulary.
CAMEO_ROOT_TO_SIGNAL = {
    "01": None,                         # public statement — no direct signal
    "02": None,                         # appeal — no direct signal
    "03": "SIG_DIP_COOPERATION",        # intent to cooperate
    "04": "SIG_DIP_CONSULTATION",       # consult
    "05": "SIG_DIP_COOPERATION",        # diplomatic cooperation
    "06": "SIG_MATERIAL_COOPERATION",   # material cooperation
    "07": "SIG_AID_PROVIDED",           # provide aid
    "08": "SIG_CONCESSION",            # yield
    "09": None,                         # investigate — no direct signal
    "10": "SIG_DEMAND_ESCALATION",      # demand
    "11": "SIG_DIP_HOSTILE_RHETORIC",   # disapprove
    "12": "SIG_NEGOTIATION_BREAKDOWN",  # reject
    "13": "SIG_MIL_THREAT",            # threaten
    "14": "SIG_INTERNAL_INSTABILITY",   # protest
    "15": "SIG_FORCE_POSTURE",          # exhibit force posture
    "16": "SIG_DIP_BREAKDOWN",          # reduce relations
    "17": "SIG_COERCION",              # coerce
    "18": "SIG_MIL_CLASH",            # assault
    "19": "SIG_MIL_CLASH",            # fight
    "20": "SIG_MASS_VIOLENCE",          # unconventional mass violence
}


def map_to_cameo(events: Iterable[str]) -> List[str]:
    """Map event labels or CAMEO codes to system signal tokens."""
    seen = set()
    signals: List[str] = []
    for event in list(events or []):
        token = str(event or "").strip().upper()
        if not token:
            continue

        # Try text-label first (e.g. "MOBILIZATION")
        signal = CAMEO_SIGNAL_MAP.get(token)

        # Then try CAMEO root code (e.g. "15", "19")
        if not signal:
            signal = CAMEO_ROOT_TO_SIGNAL.get(token)
            # Also try extracting root code from full event codes (e.g. "1384" -> "13")
            if not signal and len(token) >= 2 and token[:2].isdigit():
                signal = CAMEO_ROOT_TO_SIGNAL.get(token[:2])

        if not signal:
            continue
        if signal in seen:
            continue
        seen.add(signal)
        signals.append(signal)
    return signals


__all__ = ["CAMEO_SIGNAL_MAP", "CAMEO_ROOT_TO_SIGNAL", "map_to_cameo"]


