"""
Early-warning momentum index for near-term escalation dynamics.
"""

from __future__ import annotations

from typing import Any, Dict


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clip01(value: Any) -> float:
    return max(0.0, min(1.0, _safe_float(value, 0.0)))


def compute_emi(
    state_context: Any,
    trend: Dict[str, float],
    *,
    prewar_detected: bool = False,
) -> float:
    """
    Escalation Momentum Index (EMI).
    Positive values imply increasing escalation pressure.
    """
    # Base analytical posture from current state.
    base = _clip01(getattr(state_context, "net_escalation", 0.0))

    # Temporal momentum contribution.
    trend = dict(trend or {})
    capability = _safe_float(trend.get("capability_trend", 0.0))
    intent = _safe_float(trend.get("intent_trend", 0.0))
    stability = -_safe_float(trend.get("stability_trend", 0.0))  # instability rising
    conflict = _safe_float(trend.get("conflict_trend", 0.0))
    trend_boost = (
        0.35 * capability
        + 0.35 * intent
        + 0.20 * stability
        + 0.10 * conflict
    )
    trend_boost = max(0.0, trend_boost)

    emi = base + min(0.35, trend_boost)

    # Ordered pre-war chain boost.
    if bool(prewar_detected):
        emi += 0.35

    # Mobilization/capability acceleration boost.
    capability_index = _clip01(getattr(state_context, "capability_index", 0.0))
    mobilization_level = _clip01(getattr(getattr(state_context, "military", None), "mobilization_level", 0.0))
    if max(capability_index, mobilization_level) > 0.70:
        emi += 0.25

    return round(_clip01(emi), 3)


__all__ = ["compute_emi"]
