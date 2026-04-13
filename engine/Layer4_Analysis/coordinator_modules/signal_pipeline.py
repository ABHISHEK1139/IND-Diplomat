"""
Signal Pipeline — Signal-related helpers extracted from coordinator logic.

Re-exports coordinator internals for clean external usage without
modifying the coordinator itself.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Set, Tuple

from engine.Layer3_StateModel.signal_registry import canonicalize, SIGNAL_DIMENSION

logger = logging.getLogger("Layer4_Analysis.coordinator_modules.signal_pipeline")


def _as_state_context(candidate: Any) -> Any:
    if candidate is None:
        return None
    # If this looks like a CouncilSession, use its state_context.
    if hasattr(candidate, "state_context"):
        return getattr(candidate, "state_context", None)
    return candidate


def _as_pressure_map(session: Any, fallback: Any = None) -> Dict[str, float]:
    # Preferred source: session.pressures
    pressures = getattr(session, "pressures", None)
    if isinstance(pressures, dict):
        return dict(pressures)
    # Compatibility: caller may pass a pressure map in the old third arg.
    if isinstance(fallback, dict):
        return dict(fallback)
    return {}


def build_signal_belief_maps(
    session: Any,
    projected_signals: Dict[str, Any] | None = None,
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
    """
    Build signal → confidence and signal → source-list maps.

    Delegates to ``CouncilCoordinator._build_signal_belief_maps``
    while providing a clean module-level API.
    """
    from engine.Layer4_Analysis.coordinator import CouncilCoordinator
    coord = CouncilCoordinator()
    # The coordinator expects a StateContext-like object.
    state_context = _as_state_context(session)
    return coord._build_signal_belief_maps(state_context)


def ensure_pressure_derived_signals(
    session: Any,
    state_context: Any,
    signal_confidence: Dict[str, float] | None = None,
    observed_signals: Any | None = None,
) -> None:
    """
    Inject pressure-derived synthetic signals from state dimensions.

    Wraps ``CouncilCoordinator._ensure_pressure_derived_signals``.
    """
    from engine.Layer4_Analysis.coordinator import CouncilCoordinator
    coord = CouncilCoordinator()
    # Coordinator signature: (state_context, pressure_map)
    pressure_map = _as_pressure_map(session, fallback=signal_confidence)
    coord._ensure_pressure_derived_signals(state_context, pressure_map)


def observed_signals_from_beliefs(
    session: Any,
    projected_signals: Dict[str, Any] | None = None,
) -> List[str]:
    """
    Map accumulated beliefs back to observed signals dict.

    Wraps ``CouncilCoordinator._observed_signals_from_beliefs``.
    """
    from engine.Layer4_Analysis.coordinator import CouncilCoordinator
    coord = CouncilCoordinator()
    # Coordinator signature: (belief_map, *, threshold)
    state_context = _as_state_context(session)
    belief_map, _, _ = coord._build_signal_belief_maps(state_context)
    threshold = float(getattr(coord, "MATCHED_BELIEF_THRESHOLD", 0.20))
    return coord._observed_signals_from_beliefs(belief_map, threshold=threshold)


def collect_missing_signals(session: Any) -> List[str]:
    """
    Identify signals the analysis still needs.

    Wraps ``CouncilCoordinator._collect_missing_signals``.
    """
    from engine.Layer4_Analysis.coordinator import CouncilCoordinator
    coord = CouncilCoordinator()
    return coord._collect_missing_signals(session)


def normalize_signal_batch(tokens: List[str]) -> List[str]:
    """
    Canonicalize a batch of signal tokens using the central registry.

    This is a **pre-processing layer** — it runs before signals
    reach any downstream module.
    """
    seen: Set[str] = set()
    result: List[str] = []
    for t in tokens:
        canonical = canonicalize(t)
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


def group_by_dimension(tokens: List[str]) -> Dict[str, List[str]]:
    """Group canonical signal tokens by SRE dimension."""
    buckets: Dict[str, List[str]] = {}
    for t in tokens:
        dim = SIGNAL_DIMENSION.get(canonicalize(t), "UNKNOWN")
        buckets.setdefault(dim, []).append(t)
    return buckets
