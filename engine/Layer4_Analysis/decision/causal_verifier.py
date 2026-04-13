"""
Causal validity checks for Layer-4 hypotheses.

This module scores whether a hypothesis explains observed signals and
whether it has unique explanatory support relative to competing hypotheses.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set

from engine.Layer4_Analysis.evidence.signal_ontology import canonicalize_signal_token


def _normalize_signal_set(signals: Iterable[Any]) -> Set[str]:
    normalized: Set[str] = set()
    for item in list(signals or []):
        raw = str(item or "").strip()
        if not raw:
            continue
        token = canonicalize_signal_token(raw) or raw.upper().replace("-", "_").replace(" ", "_")
        if token:
            normalized.add(token)
    return normalized


def causal_support(hypothesis: Any, observed_signals: Iterable[Any]) -> float:
    """
    Fraction of hypothesis predictions supported by observed signals.
    """
    predicted = _normalize_signal_set(getattr(hypothesis, "predicted_signals", []) or [])
    observed = _normalize_signal_set(observed_signals or [])

    if not predicted:
        return 0.0
    return len(predicted & observed) / len(predicted)


def exclusivity_score(
    hypothesis: Any,
    all_hypotheses: Iterable[Any],
    observed_signals: Iterable[Any],
) -> float:
    """
    How much observed evidence supports this hypothesis uniquely.
    """
    unique_support = _normalize_signal_set(getattr(hypothesis, "predicted_signals", []) or [])
    observed = _normalize_signal_set(observed_signals or [])

    for other in list(all_hypotheses or []):
        if other is hypothesis:
            continue
        unique_support -= _normalize_signal_set(getattr(other, "predicted_signals", []) or [])

    if not unique_support:
        return 0.0
    return len(unique_support & observed) / len(unique_support)


def _session_observed_signals(session: Any) -> Set[str]:
    state_ctx = getattr(session, "state_context", None)
    observed = []
    if state_ctx is not None:
        observed = list(getattr(state_ctx, "observed_signals", []) or [])
    if not observed:
        observed = list(getattr(session, "evidence_log", []) or [])
    return _normalize_signal_set(observed)


def logical_verification(session: Any, observed_signals: Iterable[Any] | None = None) -> float:
    """
    Logical grounding score in [0,1].
    Combines:
    - causal support (60%)
    - exclusivity support (40%)
    """
    hypotheses = list(getattr(session, "hypotheses", []) or [])
    if not hypotheses:
        return 0.0

    observed = _normalize_signal_set(observed_signals) if observed_signals is not None else _session_observed_signals(session)
    if not observed:
        return 0.0

    scores: List[float] = []
    for h in hypotheses:
        support = causal_support(h, observed)
        exclusive = exclusivity_score(h, hypotheses, observed)
        score = (0.6 * support) + (0.4 * exclusive)
        scores.append(max(0.0, min(1.0, float(score))))

    if not scores:
        return 0.0
    return max(scores)


def logical_verification_details(session: Any, observed_signals: Iterable[Any] | None = None) -> Dict[str, Any]:
    """
    Per-hypothesis logical grounding breakdown for diagnostics.
    """
    hypotheses = list(getattr(session, "hypotheses", []) or [])
    observed = _normalize_signal_set(observed_signals) if observed_signals is not None else _session_observed_signals(session)

    rows: List[Dict[str, Any]] = []
    for h in hypotheses:
        support = causal_support(h, observed)
        exclusive = exclusivity_score(h, hypotheses, observed)
        score = max(0.0, min(1.0, float((0.6 * support) + (0.4 * exclusive))))
        rows.append(
            {
                "minister": str(getattr(h, "minister", "UNKNOWN") or "UNKNOWN"),
                "dimension": str(getattr(h, "dimension", "UNKNOWN") or "UNKNOWN"),
                "support": round(float(support), 6),
                "exclusive": round(float(exclusive), 6),
                "score": round(float(score), 6),
            }
        )

    overall = max((row["score"] for row in rows), default=0.0)
    return {
        "logic_score": round(float(overall), 6),
        "observed_signal_count": len(observed),
        "hypothesis_scores": rows,
    }


__all__ = [
    "causal_support",
    "exclusivity_score",
    "logical_verification",
    "logical_verification_details",
]

