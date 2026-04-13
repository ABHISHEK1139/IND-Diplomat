"""
Evidence Tracker Module.
Extracts graded signals from Layer-3 StateContext telemetry using the
FuzzyStateInterpreter and signal ontology.  Returns ``Dict[str, float]``
mapping signal names (both canonical *and* legacy aliases) to a confidence
score in [0..1].  The ``in`` operator on the returned dict is fully
compatible with all call-sites that previously checked membership in a set.
"""

from typing import Set, Dict, Any
from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.evidence.signal_mapper import map_and_check_signal
from engine.Layer4_Analysis.evidence.signal_ontology import (
    check_signal,
    canonicalize_signal_token,
    legacy_aliases_for_signal,
    CANONICAL_SIGNALS,
    CANONICAL_TO_LEGACY,
    score_signal_from_interpretation,
)
from engine.Layer4_Analysis.evidence.fuzzy_state_interpreter import FuzzyStateInterpreter

# Minimum score for a signal to be considered present.
_PRESENCE_THRESHOLD = 0.10


def extract_signals_from_state(ctx: StateContext | Dict[str, Any]) -> Dict[str, float]:
    """
    Compute graded signal strengths from Layer-3 StateContext telemetry.

    Combines three sources (highest score wins per token):
      1. Active fuzzy interpretation of telemetry via FuzzyStateInterpreter
         + SIGNAL_SCORE_ONTOLOGY  (always computed).
      2. Pre-existing ``signal_confidence`` dict on the StateContext.
      3. Pre-existing ``observed_signals`` set (treated as strength 1.0).

    Returns a dict whose keys include both canonical SIG_* tokens and their
    legacy aliases (e.g. "troop_staging", "logistics_movement") so that
    downstream ``token in result`` checks work regardless of naming convention.
    """
    graded: Dict[str, float] = {}

    if not ctx:
        return graded

    # ── 1. Active fuzzy scoring ──────────────────────────────────────────
    try:
        interpreted = FuzzyStateInterpreter.interpret(ctx)
    except Exception:
        interpreted = {}

    if interpreted:
        for canonical_token in CANONICAL_SIGNALS:
            score = score_signal_from_interpretation(canonical_token, interpreted)
            if score >= _PRESENCE_THRESHOLD:
                graded[canonical_token] = score
                # Propagate to every legacy alias at the same score.
                for alias in CANONICAL_TO_LEGACY.get(canonical_token, []):
                    if alias != canonical_token:
                        graded[alias] = max(graded.get(alias, 0.0), score)

    # ── 2. Fold in pre-existing signal_confidence ────────────────────────
    if isinstance(ctx, dict):
        raw_confidence = ctx.get("signal_confidence", {})
    else:
        raw_confidence = getattr(ctx, "signal_confidence", {})

    for token, value in dict(raw_confidence or {}).items():
        label = str(token or "").strip()
        if not label:
            continue
        val = max(0.0, min(1.0, float(value or 0.0)))
        if val >= _PRESENCE_THRESHOLD:
            graded[label] = max(graded.get(label, 0.0), val)

    # ── 3. Fold in pre-existing observed_signals (strength 1.0) ──────────
    if isinstance(ctx, dict):
        raw_observed = ctx.get("observed_signals", [])
    else:
        raw_observed = getattr(ctx, "observed_signals", [])

    for token in list(raw_observed or []):
        label = str(token or "").strip()
        if label:
            graded[label] = max(graded.get(label, 0.0), 1.0)

    return graded


def extract_observed_signals(state_context_dict: Dict[str, Any]) -> Dict[str, float]:
    """
    Wrapper for dictionary input (from CouncilSession or legacy calls).
    """
    try:
        ctx = StateContext.from_dict(state_context_dict)
        return extract_signals_from_state(ctx)
    except Exception:
        # Fallback if structure doesn't match
        return {}

def verify_predicted_signal(signal_name: str, ctx: StateContext) -> bool:
    """
    Verifies if a specific signal predicted by a minister exists in the state.
    Uses the Signal Mapper for semantic translation.
    """
    # 1. Check direct State extraction matches (Legacy support)
    extracted = extract_signals_from_state(ctx)
    token = str(signal_name or "").strip()
    if token in extracted:
        return True

    canonical = canonicalize_signal_token(token)
    if canonical and canonical in extracted:
        return True

    if canonical:
        for alias in legacy_aliases_for_signal(canonical):
            if alias in extracted:
                return True

    if token.lower() in extracted:
        return True

    if check_signal(token, ctx):
        return True
        
    # 2. Use Semantic Mapper (The Fix)
    return map_and_check_signal(signal_name, ctx)
