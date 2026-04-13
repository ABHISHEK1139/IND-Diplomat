"""
Epistemic confidence model.

Separates certainty-of-knowledge from escalation severity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clip01(value: Any) -> float:
    return max(0.0, min(1.0, _safe_float(value, 0.0)))


def _parse_timestamp(value: Any) -> datetime | None:
    token = str(value or "").strip()
    if not token:
        return None
    try:
        if len(token) == 10 and token[4] == "-" and token[7] == "-":
            return datetime.fromisoformat(token).replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def compute_epistemic_confidence(session: Any) -> float:
    atoms = list(getattr(session, "evidence_atoms", []) or [])
    if not atoms:
        return 0.0

    # 1) independent source count
    count_score = min(len(atoms) / 4.0, 1.0)

    # 2) source diversity
    types = {
        str(getattr(a, "source_type", "") or "").strip().lower()
        for a in atoms
        if str(getattr(a, "source_type", "") or "").strip()
    }
    diversity_score = min(len(types) / 3.0, 1.0)

    # 3) freshness (rolling one-year decay)
    now = datetime.now(timezone.utc)
    freshness_values = []
    for atom in atoms:
        parsed = _parse_timestamp(getattr(atom, "timestamp", ""))
        if parsed is None:
            freshness_values.append(0.2)
            continue
        days = max(0, int((now - parsed).days))
        freshness_values.append(max(0.0, 1.0 - (days / 365.0)))
    freshness_score = sum(freshness_values) / max(len(freshness_values), 1)

    confidence = (0.4 * count_score) + (0.3 * diversity_score) + (0.3 * freshness_score)
    return round(_clip01(confidence), 3)


__all__ = ["compute_epistemic_confidence"]
