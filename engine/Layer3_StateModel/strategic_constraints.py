"""
Strategic inhibitor model for escalation realism.

Escalation pressure is reduced by structural constraints that make
state action costly or politically difficult.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _clip01(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value or 0.0)))
    except Exception:
        return 0.0


def _logistics_scale(label: Any) -> float:
    token = str(label or "").strip().lower()
    if token in {"high", "surge", "strained", "critical"}:
        return 0.8
    if token in {"medium", "normal", "moderate"}:
        return 0.5
    if token in {"low", "none"}:
        return 0.2
    return 0.4


@dataclass
class StrategicConstraints:
    economic_risk: float = 0.0
    political_risk: float = 0.0
    international_pressure: float = 0.0
    military_readiness_cost: float = 0.0

    def __post_init__(self) -> None:
        self.economic_risk = _clip01(self.economic_risk)
        self.political_risk = _clip01(self.political_risk)
        self.international_pressure = _clip01(self.international_pressure)
        self.military_readiness_cost = _clip01(self.military_readiness_cost)

    def total_constraint(self) -> float:
        return max(
            0.0,
            min(
                1.0,
                (self.economic_risk * 0.35)
                + (self.political_risk * 0.25)
                + (self.international_pressure * 0.25)
                + (self.military_readiness_cost * 0.15),
            ),
        )

    def to_dict(self) -> dict:
        return {
            "economic_risk": self.economic_risk,
            "political_risk": self.political_risk,
            "international_pressure": self.international_pressure,
            "military_readiness_cost": self.military_readiness_cost,
            "total_constraint": self.total_constraint(),
        }

    @classmethod
    def from_any(cls, value: Any) -> "StrategicConstraints":
        if isinstance(value, StrategicConstraints):
            return value
        payload = dict(value or {}) if isinstance(value, dict) else {}
        return cls(
            economic_risk=payload.get("economic_risk", 0.0),
            political_risk=payload.get("political_risk", 0.0),
            international_pressure=payload.get("international_pressure", 0.0),
            military_readiness_cost=payload.get("military_readiness_cost", 0.0),
        )


def compute_constraints(state_context: Any) -> StrategicConstraints:
    """
    Build constraints from currently available Layer-3 interpreted fields.
    Uses direct values when present and falls back to robust proxies.
    """
    if state_context is None:
        return StrategicConstraints()

    military = getattr(state_context, "military", None)
    economic = getattr(state_context, "economic", None)
    diplomatic = getattr(state_context, "diplomatic", None)
    domestic = getattr(state_context, "domestic", None)
    capability = getattr(state_context, "capability", None)

    forex_reserves = getattr(economic, "forex_reserves", None)
    if forex_reserves is None:
        forex_reserves = getattr(economic, "trade_dependency", None)
    if forex_reserves is None:
        forex_reserves = 0.5
    economic_risk = 1.0 - _clip01(forex_reserves)

    instability = getattr(domestic, "instability", None)
    if instability is None:
        instability = getattr(domestic, "unrest", None)
    if instability is None:
        instability = 0.0
    political_risk = _clip01(instability)

    sanctions = getattr(diplomatic, "sanctions", None)
    if sanctions is None:
        sanctions = getattr(economic, "sanctions", None)
    if sanctions is None:
        sanctions = getattr(diplomatic, "hostility_tone", 0.0)
    international_pressure = _clip01(sanctions)

    logistics_strain = getattr(military, "logistics_strain", None)
    if logistics_strain is None:
        mobilization = _clip01(getattr(military, "mobilization_level", 0.0))
        exercises = _clip01((getattr(military, "exercises", 0) or 0) / 10.0)
        logistics_activity = _logistics_scale(getattr(capability, "logistics_activity", "normal"))
        logistics_strain = (mobilization * 0.55) + (exercises * 0.25) + (logistics_activity * 0.20)
    military_readiness_cost = _clip01(logistics_strain)

    return StrategicConstraints(
        economic_risk=economic_risk,
        political_risk=political_risk,
        international_pressure=international_pressure,
        military_readiness_cost=military_readiness_cost,
    )

