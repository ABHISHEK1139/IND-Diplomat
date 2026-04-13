"""
Strategic pressure translation layer.

Converts raw Layer-3 indicators into latent strategic pressures consumed by
Layer-4 ministers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


def _pick(root: Any, path: str, default: Any = 0.0) -> Any:
    current = root
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            current = getattr(current, key, default)
        if current is default:
            return default
    return current


def _as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"high", "active", "true", "yes"}:
            return 1.0
        if token in {"medium", "moderate", "normal"}:
            return 0.6
        if token in {"low", "inactive", "none", "false", "no"}:
            return 0.0
    try:
        return float(value)
    except Exception:
        return float(default)


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value or 0.0)))


def _stance_threat_value(state: Any) -> float:
    stance = str(_pick(state, "diplomatic.official_stance", "") or "").strip().lower()
    if not stance:
        return 0.0
    if any(token in stance for token in ("hostile", "threat", "aggress", "escalat", "coerc")):
        return 1.0
    if any(token in stance for token in ("guarded", "tense", "warning")):
        return 0.6
    return 0.2


@dataclass
class StrategicPressure:
    intent_pressure: float
    capability_pressure: float
    stability_pressure: float
    economic_pressure: float

    def __post_init__(self) -> None:
        self.intent_pressure = _clip01(self.intent_pressure)
        self.capability_pressure = _clip01(self.capability_pressure)
        self.stability_pressure = _clip01(self.stability_pressure)
        self.economic_pressure = _clip01(self.economic_pressure)

    def to_dict(self) -> Dict[str, float]:
        return {
            "intent_pressure": float(self.intent_pressure),
            "capability_pressure": float(self.capability_pressure),
            "stability_pressure": float(self.stability_pressure),
            "economic_pressure": float(self.economic_pressure),
        }


def map_state_to_pressures(state: Any) -> StrategicPressure:
    """
    Map raw state indicators to latent strategic pressures.
    """
    hostile_rhetoric = _clip01(
        max(
            _as_float(_pick(state, "diplomatic.hostile_rhetoric", 0.0), 0.0),
            _as_float(_pick(state, "diplomatic.hostility_tone", 0.0), 0.0),
            _as_float(_pick(state, "diplomatic.hostility", 0.0), 0.0),
        )
    )
    diplomatic_breakdown = _clip01(
        1.0 - _clip01(_as_float(_pick(state, "diplomatic.negotiations", 0.5), 0.5))
    )
    threat_statements = _clip01(_stance_threat_value(state))

    troop_movement = _clip01(
        max(
            _as_float(_pick(state, "military.troop_movement", 0.0), 0.0),
            _as_float(_pick(state, "military.mobilization_level", 0.0), 0.0),
            _as_float(_pick(state, "military.mobilization", 0.0), 0.0),
        )
    )
    exercises_raw = _as_float(_pick(state, "military.military_exercises", _pick(state, "military.exercises", 0.0)), 0.0)
    military_exercises = _clip01(exercises_raw if exercises_raw <= 1.0 else (exercises_raw / 5.0))
    force_readiness = _clip01(
        max(
            _as_float(_pick(state, "military.force_readiness", 0.0), 0.0),
            _as_float(_pick(state, "capability.troop_mobilization", 0.0), 0.0),
            _as_float(_pick(state, "capability.logistics_activity", 0.0), 0.0),
            _as_float(_pick(state, "capability.cyber_activity", 0.0), 0.0),
        )
    )

    protests = _clip01(
        max(
            _as_float(_pick(state, "domestic.protests", 0.0), 0.0),
            _as_float(_pick(state, "domestic.unrest", 0.0), 0.0),
        )
    )
    regime_fragility = _clip01(
        max(
            _as_float(_pick(state, "domestic.regime_fragility", 0.0), 0.0),
            1.0 - _clip01(_as_float(_pick(state, "domestic.regime_stability", 0.5), 0.5)),
        )
    )
    elite_conflict = _clip01(
        max(
            _as_float(_pick(state, "domestic.elite_conflict", 0.0), 0.0),
            _as_float(_pick(state, "meta.event_volatility", 0.0), 0.0),
        )
    )

    sanctions = _clip01(_as_float(_pick(state, "economic.sanctions", 0.0), 0.0))
    trade_shock = _clip01(
        max(
            _as_float(_pick(state, "economic.trade_shock", 0.0), 0.0),
            _as_float(_pick(state, "economic.economic_pressure", 0.0), 0.0),
            1.0 - _clip01(_as_float(_pick(state, "economic.trade_dependency", 0.5), 0.5)),
        )
    )
    currency_crisis = _clip01(
        max(
            _as_float(_pick(state, "economic.currency_crisis", 0.0), 0.0),
            _as_float(_pick(state, "economic.economic_pressure", 0.0), 0.0),
        )
    )

    return StrategicPressure(
        intent_pressure=_clip01(
            (0.5 * hostile_rhetoric)
            + (0.4 * diplomatic_breakdown)
            + (0.3 * threat_statements)
        ),
        capability_pressure=_clip01(
            (0.6 * troop_movement)
            + (0.5 * military_exercises)
            + (0.4 * force_readiness)
        ),
        stability_pressure=_clip01(
            (0.7 * protests)
            + (0.5 * regime_fragility)
            + (0.3 * elite_conflict)
        ),
        economic_pressure=_clip01(
            (0.6 * sanctions)
            + (0.5 * trade_shock)
            + (0.4 * currency_crisis)
        ),
    )


__all__ = ["StrategicPressure", "map_state_to_pressures"]

