"""
Enhanced Fuzzy Logic Library
=============================
Provides fuzzy membership functions for Layer-3 State Model and
Layer-4 Verification. All functions return values bounded in [0.0, 1.0].
"""

import math

def _clamp(val: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, val))


def trapezoid(x: float, a: float, b: float, c: float, d: float) -> float:
    """
    Trapezoidal membership function.
    Returns 1.0 between b and c. Rises from a to b. Falls from c to d.
    """
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if a < x < b:
        return (x - a) / (b - a) if (b - a) != 0 else 1.0
    return (d - x) / (d - c) if (d - c) != 0 else 1.0


def triangle(x: float, a: float, b: float, c: float) -> float:
    """
    Triangular membership function.
    Returns 1.0 at b. Rises from a to b. Falls from b to c.
    """
    return trapezoid(x, a, b, b, c)


def rising(x: float, low: float, high: float) -> float:
    """
    Rising linear membership function (S-curve approximation).
    Returns 0.0 below low, 1.0 above high, linearly interpolates between.
    """
    if x <= low:
        return 0.0
    if x >= high:
        return 1.0
    return (x - low) / (high - low) if (high - low) != 0 else 1.0


def falling(x: float, low: float, high: float) -> float:
    """
    Falling linear membership function.
    Returns 1.0 below low, 0.0 above high, linearly interpolates between.
    """
    if x <= low:
        return 1.0
    if x >= high:
        return 0.0
    return 1.0 - ((x - low) / (high - low)) if (high - low) != 0 else 0.0


def gaussian(x: float, center: float, sigma: float) -> float:
    """
    Gaussian membership function.
    """
    if sigma == 0:
        return 1.0 if x == center else 0.0
    return math.exp(-0.5 * ((x - center) / sigma) ** 2)


def fuzzy_and(*values: float) -> float:
    """Zadeh AND (minimum)."""
    if not values:
        return 0.0
    return min(values)


def fuzzy_or(*values: float) -> float:
    """Zadeh OR (maximum)."""
    if not values:
        return 0.0
    return max(values)


def fuzzy_not(value: float) -> float:
    """Fuzzy NOT complement."""
    return _clamp(1.0 - value)


def defuzzify_centroid(memberships: dict) -> float:
    """
    Centroid defuzzification (Weighted Average).
    memberships: dict of value -> weight
    """
    if not memberships:
        return 0.0
    
    numerator = sum(value * weight for value, weight in memberships.items())
    denominator = sum(memberships.values())
    
    if denominator == 0:
        return 0.0
    return _clamp(numerator / denominator)
