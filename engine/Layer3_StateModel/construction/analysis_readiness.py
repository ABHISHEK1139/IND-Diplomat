"""
Layer-3 analysis readiness lock.

This module decides whether Layer-4 is allowed to reason on top of the
current state model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence


MIN_CONFIDENCE = 0.45
MIN_OBSERVATIONS = 25
MIN_RECENT_ACTIVITY_SIGNALS = 10


@dataclass
class AnalysisReadinessReport:
    ready: bool
    confidence: float
    observation_count: int
    recent_activity_signals: int
    thresholds: Dict[str, float]
    blockers: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ready": self.ready,
            "confidence": round(self.confidence, 4),
            "observation_count": int(self.observation_count),
            "recent_activity_signals": int(self.recent_activity_signals),
            "thresholds": self.thresholds,
            "blockers": self.blockers,
            "details": self.details,
        }


def ready_for_analysis(
    country_state: Any,
    relationship_state: Any = None,
    confidence: float | None = None,
) -> bool:
    """
    Fast boolean gate used before invoking Layer-4.
    """
    return evaluate_analysis_readiness(
        country_state=country_state,
        relationship_state=relationship_state,
        confidence=confidence,
    ).ready


def evaluate_analysis_readiness(
    country_state: Any,
    relationship_state: Any = None,
    confidence: float | None = None,
) -> AnalysisReadinessReport:
    states = _as_state_list(country_state)
    resolved_confidence = _resolve_confidence(states, confidence)
    observation_count = _resolve_observation_count(relationship_state, states)
    recent_activity = _resolve_recent_activity_signals(states)

    blockers: List[str] = []
    if resolved_confidence < MIN_CONFIDENCE:
        blockers.append(
            f"Confidence below threshold ({resolved_confidence:.2f} < {MIN_CONFIDENCE:.2f})."
        )
    if observation_count < MIN_OBSERVATIONS:
        blockers.append(
            f"Observation coverage too low ({observation_count} < {MIN_OBSERVATIONS})."
        )
    if recent_activity < MIN_RECENT_ACTIVITY_SIGNALS:
        blockers.append(
            f"Recent activity is sparse ({recent_activity} < {MIN_RECENT_ACTIVITY_SIGNALS})."
        )

    return AnalysisReadinessReport(
        ready=(len(blockers) == 0),
        confidence=float(resolved_confidence),
        observation_count=int(observation_count),
        recent_activity_signals=int(recent_activity),
        thresholds={
            "confidence": MIN_CONFIDENCE,
            "observation_count": MIN_OBSERVATIONS,
            "recent_activity_signals": MIN_RECENT_ACTIVITY_SIGNALS,
        },
        blockers=blockers,
        details={
            "state_count": len(states),
            "relationship_state_type": type(relationship_state).__name__,
        },
    )


def _as_state_list(country_state: Any) -> List[Any]:
    if country_state is None:
        return []
    if isinstance(country_state, dict):
        if isinstance(country_state.get("states"), list):
            return [item for item in country_state["states"] if item is not None]
        return [country_state]
    if isinstance(country_state, Sequence) and not isinstance(country_state, (str, bytes)):
        return [item for item in country_state if item is not None]
    return [country_state]


def _resolve_confidence(states: List[Any], confidence: float | None) -> float:
    if confidence is not None:
        try:
            return max(0.0, min(1.0, float(confidence)))
        except Exception:
            pass

    scores: List[float] = []
    for state in states:
        direct = _lookup(state, ["analysis_confidence", "overall_score"])
        if direct is None:
            direct = _lookup(state, ["signal_breakdown", "validation_confidence", "overall_score"])
        if direct is None:
            direct = _lookup(state, ["evidence_sources", "layer3_validation_confidence"])
        if direct is None:
            continue
        try:
            scores.append(float(direct))
        except Exception:
            continue
    if not scores:
        return 0.0
    return max(0.0, min(1.0, sum(scores) / len(scores)))


def _resolve_observation_count(relationship_state: Any, states: List[Any]) -> int:
    explicit = _lookup(relationship_state, ["observation_count"])
    if explicit is not None:
        try:
            explicit_count = max(0, int(explicit))
        except Exception:
            explicit_count = 0
    else:
        explicit_count = 0

    evidence = _lookup(relationship_state, ["supporting_evidence"])
    evidence_count = 0
    if isinstance(evidence, list):
        evidence_count = len(evidence)

    confidence_observations = _lookup(relationship_state, ["confidence", "observation_count"])
    confidence_count = 0
    if confidence_observations is not None:
        try:
            confidence_count = max(0, int(confidence_observations))
        except Exception:
            confidence_count = 0

    relationship_count = max(explicit_count, evidence_count, confidence_count)
    fallback = _resolve_validated_source_observation_equivalent(states)

    if relationship_count <= 0:
        return fallback
    if relationship_count < MIN_OBSERVATIONS and fallback > relationship_count:
        return fallback
    return relationship_count


def _resolve_validated_source_observation_equivalent(states: List[Any]) -> int:
    best = 0
    for state in states:
        primary = _coerce_int(
            _lookup(state, ["signal_breakdown", "observation_quality", "primary_sensor_records"])
        )
        validated = _coerce_int(
            _lookup(state, ["signal_breakdown", "observation_quality", "validated_source_count"])
        )
        observation_records = _coerce_int(
            _lookup(state, ["signal_breakdown", "observation_quality", "observation_records"])
        )
        equivalent = max(primary, observation_records, validated * 3)
        best = max(best, equivalent)
    return max(0, best)


def _resolve_recent_activity_signals(states: List[Any]) -> int:
    total = 0
    for state in states:
        recent = _lookup(state, ["recent_activity_signals"])
        if recent is None:
            recent = _lookup(state, ["signal_breakdown", "legal_shift", "recent_signal_count"])
        if recent is None:
            recent = _lookup(state, ["signal_breakdown", "legal_signals", "signal_count"])
        if recent is None:
            continue
        try:
            total += max(0, int(recent))
        except Exception:
            continue
    return total


def _lookup(container: Any, path: List[str]) -> Any:
    current = container
    for key in path:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(key)
            continue
        if hasattr(current, key):
            current = getattr(current, key)
            continue
        return None
    return current


def _coerce_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return 0


__all__ = [
    "AnalysisReadinessReport",
    "evaluate_analysis_readiness",
    "ready_for_analysis",
    "MIN_CONFIDENCE",
    "MIN_OBSERVATIONS",
    "MIN_RECENT_ACTIVITY_SIGNALS",
]
