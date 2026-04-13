"""
Priority Intelligence Requirement (PIR) generator.

Transforms missing signals into targeted collection queries.
"""

from __future__ import annotations

from typing import Iterable, List


SIGNAL_SEARCH_MAP = {
    "SIG_MIL_MOBILIZATION": "troop movement OR reserve call-up OR mobilization army",
    "SIG_FORCE_POSTURE": "military exercise OR naval drills OR air force patrols",
    "SIG_LOGISTICS_PREP": "fuel stockpile OR military logistics buildup OR ammunition transport",
    "SIG_LOGISTICS_SURGE": "fuel stockpile OR military logistics buildup OR ammunition transport",
    "SIG_SANCTIONS_ACTIVE": "new sanctions announced OR economic sanctions imposed",
    "SIG_ECO_SANCTIONS_ACTIVE": "new sanctions announced OR economic sanctions imposed",
    "SIG_NEGOTIATION_BREAKDOWN": "talks collapsed OR negotiations failed diplomacy",
    "SIG_DIP_HOSTILITY": "official statement condemns OR warns retaliation",
    "SIG_DIP_HOSTILE_RHETORIC": "official statement condemns OR warns retaliation",
    "SIG_CYBER_ACTIVITY": "cyber attack OR cyber intrusion government network",
    "SIG_CYBER_PREPARATION": "cyber attack OR cyber intrusion government network",
    "SIG_ALLIANCE_SHIFT": "defense pact OR alliance agreement military cooperation",
}


def generate_pirs(missing_signals: Iterable[str], country: str) -> List[str]:
    queries: List[str] = []
    seen = set()
    country_token = str(country or "").strip().upper()
    for signal in list(missing_signals or []):
        token = str(signal or "").strip().upper()
        if not token:
            continue
        pattern = SIGNAL_SEARCH_MAP.get(token)
        if not pattern:
            continue
        query = f"{country_token} {pattern}".strip()
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        queries.append(query)
    return queries


__all__ = ["SIGNAL_SEARCH_MAP", "generate_pirs"]

