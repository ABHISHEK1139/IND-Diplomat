"""
Layer-3 causal signal mapping and escalation computation.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


SIGNAL_DIMENSIONS: Dict[str, str] = {
    # INTENT
    "SIG_DIP_HOSTILITY": "intent",
    "SIG_DIP_HOSTILE_RHETORIC": "intent",
    "SIG_NEGOTIATION_BREAKDOWN": "intent",
    # CAPABILITY
    "SIG_FORCE_POSTURE": "capability",
    "SIG_MIL_MOBILIZATION": "capability",
    "SIG_MIL_ESCALATION": "capability",
    "SIG_LOGISTICS_SURGE": "capability",
    # STABILITY
    "SIG_INTERNAL_INSTABILITY": "stability",
    "SIG_DOM_INTERNAL_INSTABILITY": "stability",
    "SIG_PUBLIC_PROTEST": "stability",
    "SIG_ELITE_FRACTURE": "stability",
    "SIG_MILITARY_DEFECTION": "stability",
    "SIG_PROTEST_SURGE": "stability",
    # COST / CONSTRAINTS
    "SIG_SANCTIONS_IMPOSED": "cost",
    "SIG_SANCTIONS_ACTIVE": "cost",
    "SIG_ECO_SANCTIONS_ACTIVE": "cost",
    "SIG_ECONOMIC_COLLAPSE": "cost",
    "SIG_ECON_PRESSURE": "cost",
    "SIG_ECONOMIC_PRESSURE": "cost",
}


_ACTION_DIMENSIONS: Dict[str, str] = {
    "mobilize": "capability",
    "blockade": "capability",
    "cyber_attack": "capability",
    "arms_transfer": "capability",
    "diplomacy": "intent",
    "statement": "intent",
    "consultation": "intent",
    "threaten_military": "intent",
    "protest": "stability",
    "coup_attempt": "stability",
    "election": "stability",
    "sanction": "cost",
    "trade_restriction": "cost",
    "economic_indicator": "cost",
    "trade_flow": "cost",
}


def _clip01(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value or 0.0)))
    except Exception:
        return 0.0


def _dimension_key(token: Any) -> Optional[str]:
    value = str(token or "").strip().lower()
    if value in {"capability", "intent", "stability", "cost"}:
        return value
    return None


def _empty_dimensions() -> Dict[str, float]:
    return {"capability": 0.0, "intent": 0.0, "stability": 0.0, "cost": 0.0}


def _normalize_dimensions(dimensions: Dict[str, Any]) -> Dict[str, float]:
    out = _empty_dimensions()
    for key, value in dict(dimensions or {}).items():
        normalized = _dimension_key(key)
        if not normalized:
            continue
        out[normalized] = _clip01(value)
    return out


def map_signal_dimension(signal: Any) -> Optional[str]:
    token = str(signal or "").strip().upper()
    if not token:
        return None
    return _dimension_key(SIGNAL_DIMENSIONS.get(token))


def _observation_dimension(observation: Any) -> Optional[str]:
    action = getattr(observation, "action_type", None)
    if action is None:
        return None
    action_name = str(getattr(action, "value", action) or "").strip().lower()
    return _dimension_key(_ACTION_DIMENSIONS.get(action_name))


def derive_causal_dimensions(
    *,
    base_dimensions: Optional[Dict[str, Any]] = None,
    signals: Optional[Iterable[str]] = None,
    observations: Optional[Iterable[Any]] = None,
    signal_weight: float = 0.12,
    observation_weight: float = 0.18,
) -> Dict[str, float]:
    dimensions = _normalize_dimensions(base_dimensions or {})

    for signal in list(signals or []):
        dim = map_signal_dimension(signal)
        if not dim:
            continue
        dimensions[dim] = _clip01(dimensions[dim] + signal_weight)

    for observation in list(observations or []):
        dim = _observation_dimension(observation)
        if not dim:
            continue
        intensity = _clip01(getattr(observation, "intensity", 0.0))
        dimensions[dim] = _clip01(dimensions[dim] + (observation_weight * intensity))

    return dimensions


def compute_escalation(
    capability: Any,
    intent: Any,
    stability: Any,
    cost: Any,
) -> Dict[str, float | str]:
    """
    Escalation = Drivers - Constraints.
    Drivers = 0.4*intent + 0.3*stability + 0.3*capability
    Constraints = cost
    """
    c_cap = _clip01(capability)
    c_int = _clip01(intent)
    c_stb = _clip01(stability)
    c_cost = _clip01(cost)

    pressure = (c_int * 0.4) + (c_stb * 0.3) + (c_cap * 0.3)
    net_raw = pressure - c_cost
    net = _clip01(net_raw)

    if net_raw > 0.6:
        label = "HIGH"
    elif net_raw > 0.25:
        label = "ELEVATED"
    else:
        label = "LOW"

    return {
        "risk_level": label,
        "pressure": round(_clip01(pressure), 4),
        "constraint": round(c_cost, 4),
        "net_raw": round(net_raw, 4),
        "net": round(net, 4),
        "capability": round(c_cap, 4),
        "intent": round(c_int, 4),
        "stability": round(c_stb, 4),
        "cost": round(c_cost, 4),
    }


__all__ = [
    "SIGNAL_DIMENSIONS",
    "map_signal_dimension",
    "derive_causal_dimensions",
    "compute_escalation",
]
