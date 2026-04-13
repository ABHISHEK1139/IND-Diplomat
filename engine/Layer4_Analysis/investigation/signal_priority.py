"""
Signal priority policy for investigation tasking.
"""

from __future__ import annotations

from typing import Iterable, List


SIGNAL_PRIORITY = {
    "SIG_MIL_MOBILIZATION": 10,
    "SIG_FORCE_POSTURE": 9,
    "SIG_LOGISTICS_PREP": 9,
    "SIG_LOGISTICS_SURGE": 9,
    "SIG_SANCTIONS_ACTIVE": 7,
    "SIG_ECO_SANCTIONS_ACTIVE": 7,
    "SIG_NEGOTIATION_BREAKDOWN": 6,
    "SIG_DIP_HOSTILITY": 5,
    "SIG_DIP_HOSTILE_RHETORIC": 5,
    "SIG_CYBER_ACTIVITY": 5,
    "SIG_CYBER_PREPARATION": 5,
    "SIG_INTERNAL_INSTABILITY": 4,
    "SIG_DOM_INTERNAL_INSTABILITY": 4,
    "SIG_PUBLIC_PROTEST": 2,
    "SIG_ELITE_FRACTURE": 7,
    "SIG_MILITARY_DEFECTION": 9,
}


def prioritize(signals: Iterable[str]) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    for signal in list(signals or []):
        token = str(signal or "").strip().upper()
        if not token or token in seen:
            continue
        seen.add(token)
        cleaned.append(token)
    return sorted(cleaned, key=lambda s: int(SIGNAL_PRIORITY.get(s, 1)), reverse=True)


__all__ = ["SIGNAL_PRIORITY", "prioritize"]

