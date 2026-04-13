"""
Lightweight fuzzy membership helpers for Layer-4 signal interpretation.
"""

from __future__ import annotations

from typing import Any


def _to_float(x: Any) -> float:
    if isinstance(x, bool):
        return 1.0 if x else 0.0
    try:
        return float(x)
    except Exception:
        return 0.0


def trapezoid(x: float, a: float, b: float, c: float, d: float) -> float:
    value = _to_float(x)
    if value <= a:
        return 0.0
    if a < value < b:
        denom = (b - a) if (b - a) != 0 else 1.0
        return max(0.0, min(1.0, (value - a) / denom))
    if b <= value <= c:
        return 1.0
    if c < value < d:
        denom = (d - c) if (d - c) != 0 else 1.0
        return max(0.0, min(1.0, (d - value) / denom))
    return 0.0


def rising(x: float, low: float, high: float) -> float:
    value = _to_float(x)
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    denom = (high - low) if (high - low) != 0 else 1.0
    return max(0.0, min(1.0, (value - low) / denom))


def falling(x: float, low: float, high: float) -> float:
    value = _to_float(x)
    if value <= low:
        return 1.0
    if value >= high:
        return 0.0
    denom = (high - low) if (high - low) != 0 else 1.0
    return max(0.0, min(1.0, 1.0 - ((value - low) / denom)))


__all__ = ["trapezoid", "rising", "falling"]
