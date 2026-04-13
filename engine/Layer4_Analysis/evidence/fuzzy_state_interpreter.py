"""
Fuzzy state interpreter for the Layer-4 evidence bridge.

Converts raw StateContext telemetry into graded (0..1) geopolitical features
and qualitative labels so ontology checks and minister prompts can use a shared,
stable interpretation layer.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.layer4_reasoning.fuzzy.geopolitical_sets import (
    economic_pressure_high,
    exercises_high,
    hostility_high,
    hostility_low,
    instability_high,
    mobilization_high,
    mobilization_low,
    mobilization_medium,
    negotiation_low,
    regime_stability_high,
    sanctions_high,
)


def _clamp01(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"high", "active", "yes", "true"}:
            return 1.0
        if token in {"medium", "moderate"}:
            return 0.6
        if token in {"low", "inactive", "none", "false", "no"}:
            return 0.0
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return max(0.0, min(1.0, float(default)))


def _as_state_context(state: StateContext | Dict[str, Any]) -> Optional[StateContext]:
    if isinstance(state, StateContext):
        return state
    if isinstance(state, dict):
        try:
            return StateContext.from_dict(state)
        except Exception:
            return None
    return None


def _to_band(score: float) -> str:
    value = _clamp01(score)
    if value >= 0.80:
        return "EXTREME"
    if value >= 0.60:
        return "HIGH"
    if value >= 0.35:
        return "ELEVATED"
    return "LOW"


class FuzzyStateInterpreter:
    """
    Compute fuzzy feature scores and qualitative interpretations from StateContext.
    """

    @staticmethod
    def interpret(state: StateContext | Dict[str, Any]) -> Dict[str, float]:
        ctx = _as_state_context(state)
        if ctx is None:
            return {}

        cap = ctx.capability
        mil = ctx.military
        dip = ctx.diplomatic
        eco = ctx.economic
        dom = ctx.domestic

        values: Dict[str, float] = {
            # Military
            "MIL_LOW": mobilization_low(_clamp01(mil.mobilization_level)),
            "MIL_MED": mobilization_medium(_clamp01(mil.mobilization_level)),
            "MIL_HIGH": mobilization_high(_clamp01(mil.mobilization_level)),
            "EXERCISE_HIGH": exercises_high(float(mil.exercises)),
            "CLASH_ACTIVITY": _clamp01(float(mil.clash_history) / 5.0),
            # Diplomatic
            "HOSTILITY_LOW": hostility_low(_clamp01(dip.hostility_tone)),
            "HOSTILITY_HIGH": hostility_high(_clamp01(dip.hostility_tone)),
            "NEGOTIATION_LOW": negotiation_low(_clamp01(dip.negotiations)),
            "NEGOTIATION_OPEN": _clamp01(dip.negotiations),
            "ALLIANCE_ACTIVE": _clamp01(dip.alliances),
            # Economic
            "SANCTIONS_HIGH": sanctions_high(_clamp01(eco.sanctions)),
            "ECONOMIC_PRESSURE_HIGH": economic_pressure_high(_clamp01(eco.economic_pressure)),
            "TRADE_LEVERAGE": _clamp01(eco.trade_dependency),
            # Domestic
            "UNREST_HIGH": instability_high(_clamp01(dom.unrest)),
            "PROTEST_PRESSURE": _clamp01(dom.protests),
            "REGIME_STABLE_HIGH": regime_stability_high(_clamp01(dom.regime_stability)),
            # Capability
            "CAP_TROOP_MOBILIZATION": _clamp01(cap.troop_mobilization),
            "CAP_LOGISTICS_ACTIVITY": _clamp01(cap.logistics_activity),
            "CAP_SUPPLY_STOCKPILING": _clamp01(cap.supply_stockpiling),
            "CAP_CYBER_PREPARATION": _clamp01(cap.cyber_activity),
            "CAP_EVACUATION_ACTIVITY": _clamp01(cap.evacuation_activity),
        }

        values["REGIME_INSTABILITY"] = max(0.0, 1.0 - values["REGIME_STABLE_HIGH"])
        return values

    @staticmethod
    def qualitative_view(state: StateContext | Dict[str, Any]) -> Dict[str, str]:
        fuzzy = FuzzyStateInterpreter.interpret(state)
        if not fuzzy:
            return {}

        summary_scores: Dict[str, float] = {
            "MILITARY_TENSION": max(fuzzy.get("MIL_MED", 0.0), fuzzy.get("MIL_HIGH", 0.0)),
            "FORCE_CONCENTRATION": max(
                fuzzy.get("MIL_HIGH", 0.0),
                fuzzy.get("CAP_TROOP_MOBILIZATION", 0.0),
                fuzzy.get("CLASH_ACTIVITY", 0.0),
            ),
            "LOGISTICS_SURGE": max(
                fuzzy.get("CAP_LOGISTICS_ACTIVITY", 0.0),
                fuzzy.get("EXERCISE_HIGH", 0.0),
            ),
            "DIPLOMATIC_HOSTILITY": fuzzy.get("HOSTILITY_HIGH", 0.0),
            "NEGOTIATION_STATUS": max(
                fuzzy.get("NEGOTIATION_LOW", 0.0),
                fuzzy.get("NEGOTIATION_OPEN", 0.0),
            ),
            "ALLIANCE_ACTIVITY": fuzzy.get("ALLIANCE_ACTIVE", 0.0),
            "ECONOMIC_PRESSURE": max(
                fuzzy.get("SANCTIONS_HIGH", 0.0),
                fuzzy.get("ECONOMIC_PRESSURE_HIGH", 0.0),
            ),
            "DOMESTIC_INSTABILITY": max(
                fuzzy.get("UNREST_HIGH", 0.0),
                fuzzy.get("REGIME_INSTABILITY", 0.0),
                fuzzy.get("PROTEST_PRESSURE", 0.0),
            ),
            "CYBER_PREPARATION": fuzzy.get("CAP_CYBER_PREPARATION", 0.0),
            "EVACUATION_ACTIVITY": fuzzy.get("CAP_EVACUATION_ACTIVITY", 0.0),
        }
        return {key: _to_band(score) for key, score in summary_scores.items()}

    @staticmethod
    def render_summary(
        state: StateContext | Dict[str, Any],
        *,
        keys: Optional[Iterable[str]] = None,
    ) -> str:
        view = FuzzyStateInterpreter.qualitative_view(state)
        if not view:
            return "INTERPRETED STATE:\nUnavailable"

        order: List[str] = [
            "MILITARY_TENSION",
            "FORCE_CONCENTRATION",
            "LOGISTICS_SURGE",
            "DIPLOMATIC_HOSTILITY",
            "NEGOTIATION_STATUS",
            "ALLIANCE_ACTIVITY",
            "ECONOMIC_PRESSURE",
            "DOMESTIC_INSTABILITY",
            "CYBER_PREPARATION",
            "EVACUATION_ACTIVITY",
        ]
        selected = set(keys or order)
        lines = ["INTERPRETED STATE:"]
        for key in order:
            if key not in selected or key not in view:
                continue
            label = key.replace("_", " ").title()
            lines.append(f"- {label}: {view[key]}")
        if len(lines) == 1:
            return "INTERPRETED STATE:\nUnavailable"
        return "\n".join(lines)


__all__ = ["FuzzyStateInterpreter"]

