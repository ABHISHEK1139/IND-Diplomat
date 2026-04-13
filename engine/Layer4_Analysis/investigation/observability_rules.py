"""
Observability filter for investigation tasking.
"""

from __future__ import annotations


UNOBSERVABLE_SIGNALS = {
    "SIG_SECRET_WAR_PLAN",
    "SIG_LEADER_TRUE_INTENT",
    "SIG_CLASSIFIED_STRATEGY",
}


def is_observable(signal: str) -> bool:
    token = str(signal or "").strip().upper()
    return bool(token) and token not in UNOBSERVABLE_SIGNALS


__all__ = ["UNOBSERVABLE_SIGNALS", "is_observable"]
