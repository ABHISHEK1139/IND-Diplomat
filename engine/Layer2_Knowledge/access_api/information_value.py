"""
Quantify investigation knowledge gain per extracted signal.
"""

from __future__ import annotations

from datetime import datetime, date
from math import exp
from typing import Any, Mapping


def recency_weight(signal_date: Any) -> float:
    parsed = _as_datetime(signal_date)
    if parsed is None:
        return 0.5
    days = max(0, (datetime.utcnow().date() - parsed.date()).days)
    return float(exp(-days / 60.0))


def source_weight(domain: str) -> float:
    text = str(domain or "").lower()
    if ".gov" in text or "ministry" in text or "state.gov" in text:
        return 1.0
    if "reuters" in text or "apnews" in text or "ap.org" in text:
        return 0.8
    return 0.4


def novelty_weight(is_duplicate: bool) -> float:
    return 0.05 if bool(is_duplicate) else 1.0


def information_value(signal: Any) -> float:
    """
    Return [0, 1] analytical information value for a signal-like object/dict.
    """
    domain = _get_field(signal, "source") or _get_field(signal, "domain") or "unknown"
    signal_date = _get_field(signal, "date") or _get_field(signal, "signal_date")
    is_duplicate = bool(_get_field(signal, "is_duplicate") or False)
    value = source_weight(str(domain)) * recency_weight(signal_date) * novelty_weight(is_duplicate)
    return round(max(0.0, min(1.0, float(value))), 6)


def _get_field(obj: Any, key: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10:
        text = text[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except Exception:
        pass
    if len(text) == 8 and text.isdigit():
        try:
            return datetime.strptime(text, "%Y%m%d")
        except Exception:
            pass
    return None


__all__ = [
    "recency_weight",
    "source_weight",
    "novelty_weight",
    "information_value",
]

