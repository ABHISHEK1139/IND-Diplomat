"""Domain fusion aggregates observed signals into domain-level indices.

Produces a dict with keys: capability, intent, stability, cost.
"""
from __future__ import annotations

from typing import List, Dict
from .observed_signal import ObservedSignal


def fuse_domains(signals: List[ObservedSignal]) -> Dict[str, float]:
    if not signals:
        return {"capability": 0.0, "intent": 0.0, "stability": 0.0, "cost": 0.0}

    cap = 0.0
    intent = 0.0
    stability = 0.0
    cost = 0.0
    total_weight = 0.0

    # simple heuristics: actions classified by keywords influence domains
    for s in signals:
        w = s.confidence * (0.5 + s.intensity)
        total_weight += w
        a = s.action.lower()
        if any(k in a for k in ("attack", "strike", "mobilize", "deploy")):
            cap += w * s.intensity
            intent += w * s.intensity
        if any(k in a for k in ("sanction", "tariff", "embargo", "blockade")):
            cost += w * s.intensity
            intent += w * (s.intensity * 0.6)
        if any(k in a for k in ("protest", "riot", "coup", "unrest")):
            stability += w * s.intensity
            intent += w * (s.intensity * 0.4)
        # default: small influence on capability
        cap += w * (0.2 * s.intensity)

    if total_weight <= 0:
        return {"capability": 0.0, "intent": 0.0, "stability": 0.0, "cost": 0.0}

    return {
        "capability": round(cap / total_weight, 3),
        "intent": round(intent / total_weight, 3),
        "stability": round(stability / total_weight, 3),
        "cost": round(cost / total_weight, 3),
    }
