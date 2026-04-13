def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value or 0.0)))


def triangular(x: float, a: float, b: float, c: float) -> float:
    x = float(x or 0.0)
    a = float(a)
    b = float(b)
    c = float(c)

    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if x < b:
        denom = b - a
        if denom <= 0:
            return 0.0
        return _clip01((x - a) / denom)

    denom = c - b
    if denom <= 0:
        return 0.0
    return _clip01((c - x) / denom)


def trapezoidal(x: float, a: float, b: float, c: float, d: float) -> float:
    x = float(x or 0.0)
    a = float(a)
    b = float(b)
    c = float(c)
    d = float(d)

    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if a < x < b:
        denom = b - a
        if denom <= 0:
            return 0.0
        return _clip01((x - a) / denom)

    denom = d - c
    if denom <= 0:
        return 0.0
    return _clip01((d - x) / denom)

