"""
Core fuzzy membership primitives.
"""

from __future__ import annotations

from dataclasses import dataclass


def _as_float(value: float) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


@dataclass
class FuzzySet:
    a: float
    b: float
    c: float

    def compute(self, x: float) -> float:
        # triangular membership function
        value = _as_float(x)
        if value <= self.a or value >= self.c:
            return 0.0
        if value == self.b:
            return 1.0
        if value < self.b:
            denom = (self.b - self.a) if (self.b - self.a) != 0 else 1.0
            return (value - self.a) / denom
        denom = (self.c - self.b) if (self.c - self.b) != 0 else 1.0
        return (self.c - value) / denom


# Compatibility helpers retained for existing fuzzy modules.
def triangular(x: float, a: float, b: float, c: float) -> float:
    return FuzzySet(a, b, c).compute(x)


def trapezoidal(x: float, a: float, b: float, c: float, d: float) -> float:
    value = _as_float(x)
    if value <= a or value >= d:
        return 0.0
    if b <= value <= c:
        return 1.0
    if a < value < b:
        denom = (b - a) if (b - a) != 0 else 1.0
        return (value - a) / denom
    denom = (d - c) if (d - c) != 0 else 1.0
    return (d - value) / denom


def trapezoid(x: float, a: float, b: float, c: float, d: float) -> float:
    return trapezoidal(x, a, b, c, d)


__all__ = ["FuzzySet", "triangular", "trapezoidal", "trapezoid"]
