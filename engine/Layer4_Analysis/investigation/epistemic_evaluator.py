"""
Epistemic evaluator: investigate only missing evidence that can change decisions.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable


def _dimension_coverages(hypotheses: Iterable[Any]) -> Dict[str, float]:
    dimensions = {
        "CAPABILITY": 0.0,
        "INTENT": 0.0,
        "STABILITY": 0.0,
        "COST": 0.0,
    }
    for hypothesis in list(hypotheses or []):
        dim = str(getattr(hypothesis, "dimension", "UNKNOWN") or "UNKNOWN").strip().upper()
        if dim not in dimensions:
            continue
        try:
            coverage = max(0.0, min(1.0, float(getattr(hypothesis, "coverage", 0.0) or 0.0)))
        except Exception:
            coverage = 0.0
        dimensions[dim] = max(dimensions[dim], coverage)
    return dimensions


def _decision_from_dimensions(dimensions: Dict[str, float]) -> str:
    capability = float(dimensions.get("CAPABILITY", 0.0) or 0.0)
    intent = float(dimensions.get("INTENT", 0.0) or 0.0)
    stability = float(dimensions.get("STABILITY", 0.0) or 0.0)

    if capability >= 0.6 and intent >= 0.6:
        if stability >= 0.5:
            return "HIGH"
        return "ELEVATED"
    if intent >= 0.6 and capability < 0.4:
        return "RHETORICAL_POSTURING"
    return "LOW"


def would_change_decision(session: Any, missing_signal: str) -> bool:
    """
    Returns True only when acquiring `missing_signal` could change the council decision.
    """
    token = str(missing_signal or "").strip().upper()
    if not token:
        return False

    current_dimensions = _dimension_coverages(getattr(session, "hypotheses", []) or [])
    original = (
        str(getattr(session, "final_decision", "") or "").strip().upper()
        or _decision_from_dimensions(current_dimensions)
    )

    for hypothesis in list(getattr(session, "hypotheses", []) or []):
        missing = {str(sig or "").strip().upper() for sig in list(getattr(hypothesis, "missing_signals", []) or [])}
        if token not in missing:
            continue

        predicted_count = max(len(list(getattr(hypothesis, "predicted_signals", []) or [])), 1)
        current_coverage = max(0.0, min(1.0, float(getattr(hypothesis, "coverage", 0.0) or 0.0)))
        simulated_coverage = max(0.0, min(1.0, current_coverage + (1.0 / float(predicted_count))))

        simulated_dimensions = dict(current_dimensions)
        dim = str(getattr(hypothesis, "dimension", "UNKNOWN") or "UNKNOWN").strip().upper()
        if dim in simulated_dimensions:
            simulated_dimensions[dim] = max(simulated_dimensions[dim], simulated_coverage)

        simulated_decision = _decision_from_dimensions(simulated_dimensions)
        if simulated_decision != original:
            return True
        if simulated_coverage >= 0.6:
            return True

    return False


__all__ = ["would_change_decision"]
