"""
Geopolitical fuzzy membership sets.
"""

from __future__ import annotations

from .membership import FuzzySet


# Mobilization levels
LOW_MOBILIZATION = FuzzySet(0.0, 0.2, 0.5)
MEDIUM_MOBILIZATION = FuzzySet(0.3, 0.5, 0.7)
HIGH_MOBILIZATION = FuzzySet(0.6, 0.85, 1.0)

# Diplomatic hostility
LOW_HOSTILITY = FuzzySet(0.0, 0.2, 0.4)
MEDIUM_HOSTILITY = FuzzySet(0.3, 0.5, 0.7)
HIGH_HOSTILITY = FuzzySet(0.6, 0.85, 1.0)
_COMPAT_HIGH_HOSTILITY = FuzzySet(0.5, 0.7, 1.0)

# Economic pressure
LOW_PRESSURE = FuzzySet(0.0, 0.2, 0.4)
MEDIUM_PRESSURE = FuzzySet(0.3, 0.5, 0.7)
HIGH_PRESSURE = FuzzySet(0.6, 0.85, 1.0)


# Compatibility wrappers retained for existing fuzzy bridge modules.
def mobilization_low(x: float) -> float:
    return LOW_MOBILIZATION.compute(x)


def mobilization_medium(x: float) -> float:
    return MEDIUM_MOBILIZATION.compute(x)


def mobilization_high(x: float) -> float:
    return HIGH_MOBILIZATION.compute(x)


def hostility_low(x: float) -> float:
    return LOW_HOSTILITY.compute(x)


def hostility_high(x: float) -> float:
    return max(HIGH_HOSTILITY.compute(x), _COMPAT_HIGH_HOSTILITY.compute(x))


def economic_pressure_high(x: float) -> float:
    return HIGH_PRESSURE.compute(x)


def sanctions_high(x: float) -> float:
    return HIGH_PRESSURE.compute(x)


def instability_high(x: float) -> float:
    return HIGH_HOSTILITY.compute(x)


def regime_stability_high(x: float) -> float:
    # "Stable" is modeled as inverse instability.
    return max(0.0, min(1.0, 1.0 - HIGH_HOSTILITY.compute(1.0 - float(x or 0.0))))


def exercises_high(x: float) -> float:
    # Keep monotonic behavior for existing callers.
    value = float(x or 0.0)
    return max(0.0, min(1.0, value / 6.0))


def negotiation_low(x: float) -> float:
    return HIGH_HOSTILITY.compute(1.0 - float(x or 0.0))


__all__ = [
    "LOW_MOBILIZATION",
    "MEDIUM_MOBILIZATION",
    "HIGH_MOBILIZATION",
    "LOW_HOSTILITY",
    "MEDIUM_HOSTILITY",
    "HIGH_HOSTILITY",
    "LOW_PRESSURE",
    "MEDIUM_PRESSURE",
    "HIGH_PRESSURE",
    "mobilization_low",
    "mobilization_medium",
    "mobilization_high",
    "hostility_low",
    "hostility_high",
    "economic_pressure_high",
    "sanctions_high",
    "instability_high",
    "regime_stability_high",
    "exercises_high",
    "negotiation_low",
]
