"""
Counterfactual decision testing for Layer-4 sessions.

This module evaluates whether a specific signal is causally important by
removing it and recomputing the council decision.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

from engine.Layer4_Analysis.coordinator import CouncilCoordinator
from engine.Layer4_Analysis.evidence.signal_ontology import canonicalize_signal_token


@dataclass
class CounterfactualResult:
    signal: str
    original_decision: str
    counterfactual_decision: str
    changed: bool
    original_net: float
    counterfactual_net: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal": self.signal,
            "original_decision": self.original_decision,
            "counterfactual_decision": self.counterfactual_decision,
            "changed": bool(self.changed),
            "original_net": float(self.original_net),
            "counterfactual_net": float(self.counterfactual_net),
            "delta_net": float(self.counterfactual_net - self.original_net),
        }


def _normalize_signal(signal: Any) -> str:
    """Delegate to the authoritative signal ontology normaliser."""
    canon = canonicalize_signal_token(str(signal or ""))
    return canon if canon else str(signal or "").strip().upper().replace("-", "_").replace(" ", "_")


def _clone_session(session: Any) -> Any:
    return deepcopy(session)


def _remove_signal_from_session(session: Any, signal: str) -> None:
    token = _normalize_signal(signal)
    if not token:
        return

    ctx = getattr(session, "state_context", None)
    if ctx is not None:
        observed = set(getattr(ctx, "observed_signals", set()) or set())
        if token in observed:
            observed.remove(token)
        ctx.observed_signals = observed

        confidence = dict(getattr(ctx, "signal_confidence", {}) or {})
        if token in confidence:
            confidence.pop(token, None)
        ctx.signal_confidence = confidence

        evidence = dict(getattr(ctx, "signal_evidence", {}) or {})
        if token in evidence:
            evidence.pop(token, None)
        ctx.signal_evidence = evidence

    evidence_log = [str(item or "").strip().upper() for item in list(getattr(session, "evidence_log", []) or [])]
    session.evidence_log = [item for item in evidence_log if item and item != token]

    hypotheses = list(getattr(session, "hypotheses", []) or [])
    for hypothesis in hypotheses:
        predicted = [_normalize_signal(item) for item in list(getattr(hypothesis, "predicted_signals", []) or [])]
        matched = [_normalize_signal(item) for item in list(getattr(hypothesis, "matched_signals", []) or [])]
        missing = [_normalize_signal(item) for item in list(getattr(hypothesis, "missing_signals", []) or [])]

        if token in matched:
            matched = [item for item in matched if item != token]
            if token in predicted and token not in missing:
                missing.append(token)

        matched = [item for item in matched if item]
        missing = [item for item in missing if item]
        predicted = [item for item in predicted if item]

        hypothesis.matched_signals = matched
        hypothesis.missing_signals = missing
        hypothesis.coverage = len(matched) / max(len(predicted), 1)


def recompute_decision(session: Any, coordinator: Optional[CouncilCoordinator] = None) -> str:
    runner = coordinator or CouncilCoordinator()
    decision = str(runner.compute_escalation(session))
    session.final_decision = decision
    session.king_decision = decision
    return decision


def counterfactual_test(
    session: Any,
    signal: str,
    coordinator: Optional[CouncilCoordinator] = None,
) -> CounterfactualResult:
    token = _normalize_signal(signal)
    runner = coordinator or CouncilCoordinator()

    base = _clone_session(session)
    original_decision = str(getattr(base, "final_decision", "") or "")
    if not original_decision:
        original_decision = recompute_decision(base, coordinator=runner)
    original_net = float(getattr(base, "net_escalation", 0.0) or 0.0)

    cf = _clone_session(base)
    _remove_signal_from_session(cf, token)
    counterfactual_decision = recompute_decision(cf, coordinator=runner)
    counterfactual_net = float(getattr(cf, "net_escalation", 0.0) or 0.0)

    return CounterfactualResult(
        signal=token,
        original_decision=original_decision,
        counterfactual_decision=counterfactual_decision,
        changed=bool(counterfactual_decision != original_decision),
        original_net=original_net,
        counterfactual_net=counterfactual_net,
    )


def rank_causal_signals(
    session: Any,
    signals: Optional[Iterable[str]] = None,
    coordinator: Optional[CouncilCoordinator] = None,
) -> List[Dict[str, Any]]:
    candidates: Set[str] = set()
    if signals is not None:
        for item in list(signals or []):
            token = _normalize_signal(item)
            if token:
                candidates.add(token)
    else:
        ctx = getattr(session, "state_context", None)
        for item in list(getattr(ctx, "observed_signals", set()) or set()):
            token = _normalize_signal(item)
            if token:
                candidates.add(token)

    results: List[CounterfactualResult] = []
    runner = coordinator or CouncilCoordinator()
    for token in sorted(candidates):
        results.append(counterfactual_test(session, token, coordinator=runner))

    ordered = sorted(
        results,
        key=lambda row: (
            0 if row.changed else 1,
            abs(float(row.counterfactual_net - row.original_net)),
        ),
        reverse=False,
    )
    return [row.to_dict() for row in ordered]


__all__ = [
    "CounterfactualResult",
    "counterfactual_test",
    "rank_causal_signals",
    "recompute_decision",
]

