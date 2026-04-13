"""
Deterministic evidence weighting for observed escalation signals.
"""

from __future__ import annotations

from typing import Dict, Iterable


LEGAL_SIGNALS = {
    "SIG_SOVEREIGNTY_BREACH": 0.30,
    "SIG_MARITIME_VIOLATION": 0.25,
    "SIG_ILLEGAL_COERCION": 0.20,
    "SIG_TREATY_VIOLATION": 0.30,
    "SIG_CYBER_SOVEREIGNTY_VIOLATION": 0.20,
}

# Empirical coercive-pressure signal (renamed from SIG_ILLEGAL_COERCION)
# Kept separate from LEGAL_SIGNALS — feeds SRE, not legal pipeline.
EMPIRICAL_COERCION_SIGNALS = {
    "SIG_COERCIVE_PRESSURE": 0.20,
}

MILITARY_SIGNALS = {
    "SIG_MIL_ESCALATION": 0.35,
    "SIG_BORDER_CLASH": 0.30,
    "SIG_MIL_BORDER_CLASHES": 0.30,
    "SIG_FORCE_POSTURE": 0.20,
    "SIG_MIL_MOBILIZATION": 0.40,
    "SIG_FORCE_CONCENTRATION": 0.30,
    "SIG_LOGISTICS_SURGE": 0.25,
    "SIG_LOGISTICS_PREP": 0.20,
}

ECONOMIC_SIGNALS = {
    "SIG_SANCTIONS_ACTIVE": 0.15,
    "SIG_ECO_SANCTIONS_ACTIVE": 0.15,
    "SIG_ECO_PRESSURE_HIGH": 0.12,
    "SIG_ECO_TRADE_LEVERAGE": 0.20,
    "SIG_CHOKEPOINT_CONTROL": 0.20,
    "SIG_ECONOMIC_STRESS": 0.10,
    "SIG_ECONOMIC_PRESSURE": 0.10,
    "SIG_ECON_PRESSURE": 0.10,
}

DIPLOMATIC_SIGNALS = {
    "SIG_DIP_HOSTILITY": 0.05,
    "SIG_NEGOTIATION_BREAKDOWN": 0.08,
    "SIG_DIP_HOSTILE_RHETORIC": 0.03,
}


_SIGNAL_WEIGHTS: Dict[str, float] = {}
_SIGNAL_WEIGHTS.update(LEGAL_SIGNALS)
_SIGNAL_WEIGHTS.update(MILITARY_SIGNALS)
_SIGNAL_WEIGHTS.update(ECONOMIC_SIGNALS)
_SIGNAL_WEIGHTS.update(DIPLOMATIC_SIGNALS)


def _norm(value: object) -> str:
    return str(value or "").strip().upper()


def compute_evidence_score(signals: Iterable[str]) -> float:
    """
    Aggregate weighted evidence in [0, 1].
    """
    score = 0.0
    for signal in {_norm(item) for item in list(signals or []) if _norm(item)}:
        score += float(_SIGNAL_WEIGHTS.get(signal, 0.0))
    return max(0.0, min(1.0, float(score)))


__all__ = [
    "LEGAL_SIGNALS",
    "MILITARY_SIGNALS",
    "ECONOMIC_SIGNALS",
    "DIPLOMATIC_SIGNALS",
    "compute_evidence_score",
]
