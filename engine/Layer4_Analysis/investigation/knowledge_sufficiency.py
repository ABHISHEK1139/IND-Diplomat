"""
Knowledge sufficiency gate for investigation loop termination.
"""

from __future__ import annotations

from typing import Any


def knowledge_is_sufficient(session: Any) -> bool:
    satisfied_dimensions = set()
    for hypothesis in list(getattr(session, "hypotheses", []) or []):
        try:
            coverage = float(getattr(hypothesis, "coverage", 0.0) or 0.0)
        except Exception:
            coverage = 0.0
        if coverage < 0.6:
            continue
        dim = str(getattr(hypothesis, "dimension", "UNKNOWN") or "UNKNOWN").strip().upper()
        if dim in {"CAPABILITY", "INTENT", "STABILITY", "COST"}:
            satisfied_dimensions.add(dim)

    return len(satisfied_dimensions) >= 2


__all__ = ["knowledge_is_sufficient"]
