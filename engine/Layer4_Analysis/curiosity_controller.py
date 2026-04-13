"""
Layer-4 Curiosity Controller — Active Learning Engine
=====================================================

Replaces passive PIR generation ("collect everything missing") with
**Value of Information (VOI)** driven investigation targeting.

Instead of asking "what signals are missing?", the system asks:

    "Which signal, if I learned its true value right now,
     would most change my conclusion?"

This is the module that converts IND-Diplomat from an analytical engine
into an **epistemic agent** — one that actively reduces uncertainty
in its own model of the world.

Algorithm
---------
1. Each hypothesis lists signals that would prove/disprove it.
2. For each signal, compute *uncertainty* = 1 − belief_confidence.
3. Compute **VOI(signal) = hypothesis_weight × uncertainty × impact**
   where *impact* is how much the hypothesis depends on that signal.
4. Rank signals by VOI; top-N become the investigation targets.
5. Build focused PIRs from only the high-VOI signals.

Position in Pipeline
--------------------
    state built
    → ministers deliberate
    → hypotheses generated
    → **curiosity_controller** (this module)   ← HERE
    → PIR generation (now VOI-filtered)
    → MoltBot collection
    → belief accumulator
    → re-analysis
    → judgment gate
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =====================================================================
# Signal → Hypothesis Impact Map
# =====================================================================
# How much each signal contributes to proving a hypothesis dimension.
# Values: 0.0 (irrelevant) to 1.0 (decisive).
#
# This is the *domain knowledge* that makes VOI meaningful.
# A missile test (SIG_MIL_ESCALATION) has high impact on CAPABILITY
# but low impact on COST.  A sanctions signal has high impact on COST
# but low impact on CAPABILITY.

SIGNAL_IMPACT: Dict[str, Dict[str, float]] = {
    # ── CAPABILITY dimension ──────────────────────────────────────
    "SIG_MIL_MOBILIZATION":     {"CAPABILITY": 0.90, "INTENT": 0.40, "STABILITY": 0.10, "COST": 0.05},
    "SIG_FORCE_POSTURE":        {"CAPABILITY": 0.85, "INTENT": 0.50, "STABILITY": 0.05, "COST": 0.05},
    "SIG_MIL_ESCALATION":       {"CAPABILITY": 0.95, "INTENT": 0.70, "STABILITY": 0.20, "COST": 0.10},
    "SIG_LOGISTICS_PREP":       {"CAPABILITY": 0.80, "INTENT": 0.30, "STABILITY": 0.05, "COST": 0.15},
    "SIG_LOGISTICS_SURGE":      {"CAPABILITY": 0.80, "INTENT": 0.35, "STABILITY": 0.05, "COST": 0.15},
    "SIG_CYBER_ACTIVITY":       {"CAPABILITY": 0.70, "INTENT": 0.60, "STABILITY": 0.15, "COST": 0.10},
    "SIG_CYBER_PREPARATION":    {"CAPABILITY": 0.75, "INTENT": 0.55, "STABILITY": 0.10, "COST": 0.10},
    "SIG_WMD_RISK":             {"CAPABILITY": 1.00, "INTENT": 0.80, "STABILITY": 0.30, "COST": 0.20},
    "SIG_AIRBASE_ACTIVITY":     {"CAPABILITY": 0.85, "INTENT": 0.45, "STABILITY": 0.05, "COST": 0.05},
    "SIG_DECEPTION_ACTIVITY":   {"CAPABILITY": 0.40, "INTENT": 0.75, "STABILITY": 0.20, "COST": 0.05},

    # ── INTENT dimension ──────────────────────────────────────────
    "SIG_DIP_HOSTILITY":        {"CAPABILITY": 0.10, "INTENT": 0.90, "STABILITY": 0.30, "COST": 0.15},
    "SIG_DIP_HOSTILE_RHETORIC": {"CAPABILITY": 0.05, "INTENT": 0.80, "STABILITY": 0.20, "COST": 0.10},
    "SIG_ALLIANCE_ACTIVATION":  {"CAPABILITY": 0.30, "INTENT": 0.85, "STABILITY": 0.15, "COST": 0.10},
    "SIG_ALLIANCE_SHIFT":       {"CAPABILITY": 0.25, "INTENT": 0.80, "STABILITY": 0.20, "COST": 0.15},
    "SIG_NEGOTIATION_BREAKDOWN":{"CAPABILITY": 0.05, "INTENT": 0.95, "STABILITY": 0.25, "COST": 0.20},
    "SIG_COERCIVE_BARGAINING":  {"CAPABILITY": 0.15, "INTENT": 0.85, "STABILITY": 0.15, "COST": 0.25},
    "SIG_RETALIATORY_THREAT":   {"CAPABILITY": 0.30, "INTENT": 0.90, "STABILITY": 0.20, "COST": 0.15},
    "SIG_DETERRENCE_SIGNALING": {"CAPABILITY": 0.50, "INTENT": 0.80, "STABILITY": 0.10, "COST": 0.10},
    "SIG_LEGAL_VIOLATION":      {"CAPABILITY": 0.10, "INTENT": 0.70, "STABILITY": 0.15, "COST": 0.20},
    "SIG_COERCIVE_PRESSURE":    {"CAPABILITY": 0.10, "INTENT": 0.75, "STABILITY": 0.20, "COST": 0.25},

    # ── STABILITY dimension ───────────────────────────────────────
    "SIG_INTERNAL_INSTABILITY":     {"CAPABILITY": 0.05, "INTENT": 0.25, "STABILITY": 0.95, "COST": 0.20},
    "SIG_INTERNAL_UNREST":          {"CAPABILITY": 0.05, "INTENT": 0.20, "STABILITY": 0.90, "COST": 0.15},
    "SIG_DOM_INTERNAL_INSTABILITY": {"CAPABILITY": 0.05, "INTENT": 0.25, "STABILITY": 0.95, "COST": 0.20},

    # ── COST dimension ────────────────────────────────────────────
    "SIG_ECONOMIC_PRESSURE":    {"CAPABILITY": 0.05, "INTENT": 0.20, "STABILITY": 0.30, "COST": 0.90},
    "SIG_ECO_SANCTIONS":        {"CAPABILITY": 0.05, "INTENT": 0.25, "STABILITY": 0.25, "COST": 0.95},
    "SIG_ECO_SANCTIONS_ACTIVE": {"CAPABILITY": 0.05, "INTENT": 0.30, "STABILITY": 0.25, "COST": 0.95},
    "SIG_ECO_PRESSURE_HIGH":    {"CAPABILITY": 0.05, "INTENT": 0.20, "STABILITY": 0.30, "COST": 0.90},
    "SIG_ECON_PRESSURE":        {"CAPABILITY": 0.05, "INTENT": 0.20, "STABILITY": 0.30, "COST": 0.90},
    "SIG_ECO_DEPENDENCY":       {"CAPABILITY": 0.05, "INTENT": 0.15, "STABILITY": 0.20, "COST": 0.85},
    "SIG_TRADE_DISRUPTION":     {"CAPABILITY": 0.05, "INTENT": 0.15, "STABILITY": 0.25, "COST": 0.90},
    "SIG_SANCTIONS_ACTIVE":     {"CAPABILITY": 0.05, "INTENT": 0.25, "STABILITY": 0.25, "COST": 0.95},
}

# Default impact for unknown signals (conservative — low but nonzero)
_DEFAULT_IMPACT: Dict[str, float] = {
    "CAPABILITY": 0.20, "INTENT": 0.20, "STABILITY": 0.20, "COST": 0.20,
}


# =====================================================================
# VOI Result Dataclass
# =====================================================================

@dataclass
class SignalVOI:
    """
    Value of Information for a single signal.

    Captures why the system is curious about this signal,
    how much learning it would change the analysis, and
    which hypothesis dimensions it serves.
    """
    signal: str
    voi: float                          # Aggregate VOI score
    uncertainty: float                  # 1 − current confidence
    current_confidence: float           # What we know now
    contributing_hypotheses: List[str]  # Which ministers care
    primary_dimension: str              # Dimension with highest impact
    impact_by_dimension: Dict[str, float] = field(default_factory=dict)
    reason: str = ""                    # Human-readable justification

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal": self.signal,
            "voi": round(self.voi, 4),
            "uncertainty": round(self.uncertainty, 4),
            "current_confidence": round(self.current_confidence, 4),
            "contributing_hypotheses": list(self.contributing_hypotheses),
            "primary_dimension": self.primary_dimension,
            "impact_by_dimension": {k: round(v, 4) for k, v in self.impact_by_dimension.items()},
            "reason": self.reason,
        }


@dataclass
class CuriosityPlan:
    """
    The output of the curiosity engine.

    Contains the ranked VOI targets and the focused PIR list
    that replaces the generic collection plan.
    """
    targets: List[SignalVOI] = field(default_factory=list)
    all_voi_scores: Dict[str, float] = field(default_factory=dict)
    total_signals_evaluated: int = 0
    signals_above_threshold: int = 0
    threshold: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_count": len(self.targets),
            "total_evaluated": self.total_signals_evaluated,
            "above_threshold": self.signals_above_threshold,
            "voi_threshold": round(self.threshold, 4),
            "targets": [t.to_dict() for t in self.targets],
        }


# =====================================================================
# Core VOI Computation
# =====================================================================

def compute_signal_voi(
    signal: str,
    hypotheses: List[Any],
    current_confidence: float,
) -> Tuple[float, Dict[str, float], List[str]]:
    """
    Compute the Value of Information for a single signal across
    all hypotheses.

    VOI(signal) = Σ_h [ hypothesis_weight × uncertainty × impact(signal, h.dimension) ]

    Parameters
    ----------
    signal : str
        Signal token (e.g. "SIG_MIL_MOBILIZATION").
    hypotheses : list
        Hypothesis objects from the council (have .weight, .dimension).
    current_confidence : float
        Current belief confidence in this signal (0..1).

    Returns
    -------
    (voi_score, impact_by_dimension, contributing_ministers)
    """
    uncertainty = max(0.0, 1.0 - min(1.0, current_confidence))

    if uncertainty < 0.01:
        # Already fully confident — no information value
        return 0.0, {}, []

    impact_map = SIGNAL_IMPACT.get(signal, _DEFAULT_IMPACT)
    total_voi = 0.0
    dim_contributions: Dict[str, float] = {}
    contributing: List[str] = []

    for h in hypotheses:
        h_weight = max(0.0, float(getattr(h, "weight", 0.0) or 0.0))
        if h_weight < 0.01:
            continue

        h_dim = str(getattr(h, "dimension", "UNKNOWN")).strip().upper()
        impact = impact_map.get(h_dim, 0.10)

        contribution = h_weight * uncertainty * impact

        if contribution > 0.001:
            total_voi += contribution
            dim_contributions[h_dim] = dim_contributions.get(h_dim, 0.0) + contribution
            minister = str(getattr(h, "minister", "unknown"))
            if minister not in contributing:
                contributing.append(minister)

    return total_voi, dim_contributions, contributing


# =====================================================================
# The Curiosity Engine
# =====================================================================

class CuriosityController:
    """
    Active Learning Engine — selects high-value investigation targets.

    Instead of collecting everything missing, this controller computes
    the **Value of Information** for each signal and selects only those
    whose resolution would most change the analysis outcome.

    This is the core of the observe-predict-act-compare-update loop.
    """

    def __init__(
        self,
        max_targets: int = 3,
        voi_threshold: float = 0.05,
        min_uncertainty: float = 0.10,
    ):
        """
        Parameters
        ----------
        max_targets : int
            Maximum number of high-VOI signals to select per cycle.
        voi_threshold : float
            Minimum VOI score to be considered for investigation.
        min_uncertainty : float
            Signals with uncertainty below this are skipped.
        """
        self.max_targets = max(1, max_targets)
        self.voi_threshold = max(0.0, voi_threshold)
        self.min_uncertainty = max(0.0, min_uncertainty)

    def evaluate(
        self,
        hypotheses: List[Any],
        signal_confidence: Dict[str, float],
        observed_signals: Optional[set] = None,
    ) -> CuriosityPlan:
        """
        Compute VOI for all signals relevant to the current hypotheses
        and select the top-N investigation targets.

        Parameters
        ----------
        hypotheses : list
            Hypothesis objects from council deliberation.
        signal_confidence : dict
            Current belief confidence per signal (from StateContext).
        observed_signals : set, optional
            Signals already confirmed by observation.

        Returns
        -------
        CuriosityPlan
            Ranked investigation targets with VOI scores.
        """
        if not hypotheses:
            logger.info("[CURIOSITY] No hypotheses — nothing to be curious about")
            return CuriosityPlan()

        observed = set(observed_signals or [])

        # ── 1. Collect all candidate signals from hypotheses ──────
        # Phase-2 guard: skip any signal with legal namespace
        from engine.Layer3_StateModel.signal_projection import _SIGNAL_DIMENSION
        candidate_signals: Dict[str, float] = {}
        for h in hypotheses:
            for sig_token in list(getattr(h, "predicted_signals", []) or []):
                sig = str(sig_token).strip().upper()
                if sig and sig in _SIGNAL_DIMENSION:
                    # Only empirical signals (those in the dimension table)
                    conf = float(signal_confidence.get(sig, 0.0))
                    candidate_signals[sig] = conf

            # Also include missing_signals from hypotheses
            for sig_token in list(getattr(h, "missing_signals", []) or []):
                sig = str(sig_token).strip().upper()
                if sig and sig not in candidate_signals and sig in _SIGNAL_DIMENSION:
                    candidate_signals[sig] = float(signal_confidence.get(sig, 0.0))

        if not candidate_signals:
            logger.info("[CURIOSITY] No candidate signals from hypotheses")
            return CuriosityPlan()

        # ── 2. Compute VOI for each candidate ────────────────────
        voi_results: List[SignalVOI] = []
        all_scores: Dict[str, float] = {}

        for sig, conf in candidate_signals.items():
            uncertainty = 1.0 - min(1.0, max(0.0, conf))

            # Skip near-certain signals
            if uncertainty < self.min_uncertainty:
                all_scores[sig] = 0.0
                continue

            voi_score, dim_impacts, contributors = compute_signal_voi(
                signal=sig,
                hypotheses=hypotheses,
                current_confidence=conf,
            )
            all_scores[sig] = voi_score

            if voi_score < self.voi_threshold:
                continue

            # Determine primary dimension (highest impact contribution)
            primary_dim = max(dim_impacts, key=dim_impacts.get) if dim_impacts else "UNKNOWN"

            # Build human-readable reason
            reason = (
                f"Uncertainty {uncertainty:.2f} × "
                f"hypothesis weight → VOI {voi_score:.3f}. "
                f"Primary dimension: {primary_dim}. "
                f"Would inform: {', '.join(contributors[:3])}."
            )

            voi_results.append(SignalVOI(
                signal=sig,
                voi=voi_score,
                uncertainty=uncertainty,
                current_confidence=conf,
                contributing_hypotheses=contributors,
                primary_dimension=primary_dim,
                impact_by_dimension=dim_impacts,
                reason=reason,
            ))

        # ── 3. Rank by VOI and select top-N ──────────────────────
        voi_results.sort(key=lambda r: r.voi, reverse=True)
        targets = voi_results[:self.max_targets]

        above_threshold = len(voi_results)

        plan = CuriosityPlan(
            targets=targets,
            all_voi_scores=all_scores,
            total_signals_evaluated=len(candidate_signals),
            signals_above_threshold=above_threshold,
            threshold=self.voi_threshold,
        )

        # ── 4. Log the curiosity decision ─────────────────────────
        if targets:
            lines = ["[CURIOSITY] Investigation targets selected:"]
            for i, t in enumerate(targets, 1):
                lines.append(
                    f"  {i}. {t.signal:30s} VOI={t.voi:.3f}  "
                    f"uncertainty={t.uncertainty:.2f}  "
                    f"dim={t.primary_dimension}"
                )
            lines.append(
                f"  ({above_threshold} signals above threshold, "
                f"{len(candidate_signals)} evaluated)"
            )
            logger.info("\n".join(lines))
        else:
            logger.info(
                "[CURIOSITY] No signals above VOI threshold %.3f "
                "(%d candidates evaluated)",
                self.voi_threshold, len(candidate_signals),
            )

        return plan


# =====================================================================
# VOI → PIR Bridge
# =====================================================================

def curiosity_to_pirs(
    curiosity_plan: CuriosityPlan,
    hypotheses: List[Any],
    projected_signals: Optional[Dict[str, Any]] = None,
    country: str = "",
    cycle: int = 0,
) -> Any:
    """
    Convert curiosity targets into a focused CollectionPlan.

    This replaces the generic ``build_collection_plan()`` when the
    curiosity engine is active.  Only high-VOI signals get PIRs.

    Parameters
    ----------
    curiosity_plan : CuriosityPlan
        Output of ``CuriosityController.evaluate()``.
    hypotheses : list
        Council hypotheses (passed through for gap metadata).
    projected_signals : dict, optional
        Signal projections from StateContext.
    country : str
        Target country code.
    cycle : int
        Investigation cycle number.

    Returns
    -------
    CollectionPlan
        Focused collection plan with VOI-prioritized PIRs.
    """
    from Core.intelligence.pir import (
        PIR,
        PIRPriority,
        CollectionPlan,
        BeliefGap,
        SIGNAL_COLLECTION_MODALITY,
        CollectionModality,
    )

    pirs: List[PIR] = []
    gaps: List[BeliefGap] = []
    projected = dict(projected_signals or {})

    for target in curiosity_plan.targets:
        signal = target.signal
        modalities = SIGNAL_COLLECTION_MODALITY.get(signal)
        if not modalities:
            # Unknown signal — default to OSINT
            modalities = [CollectionModality.OSINT_EVENTS]

        # Priority from VOI strength
        if target.voi >= 0.30:
            priority = PIRPriority.CRITICAL
        elif target.voi >= 0.15:
            priority = PIRPriority.HIGH
        else:
            priority = PIRPriority.ROUTINE

        # Get recency/confidence from projections
        proj = projected.get(signal)
        recency = float(getattr(proj, "recency", 1.0) or 1.0) if proj else 1.0
        confidence = target.current_confidence

        # Structured reason — includes VOI justification
        reason = (
            f"VOI={target.voi:.3f}: {target.signal} has "
            f"confidence={confidence:.3f}, uncertainty={target.uncertainty:.3f}. "
            f"Primary dimension: {target.primary_dimension}. "
            f"Hypotheses: {', '.join(target.contributing_hypotheses[:3])}."
        )

        # Issue PIR for primary modality
        pir = PIR(
            dimension=target.primary_dimension,
            signal=signal,
            collection=modalities[0],
            priority=priority,
            reason=reason,
            country=country,
            current_confidence=confidence,
            current_recency=recency,
            confidence_gap=target.uncertainty,
        )
        pirs.append(pir)

        # Build corresponding belief gap for metadata compatibility
        gaps.append(BeliefGap(
            minister=", ".join(target.contributing_hypotheses[:2]) or "curiosity",
            dimension=target.primary_dimension,
            weight=target.voi,
            coverage=confidence,
            gap_severity=target.voi,
            signals=[signal],
        ))

    plan = CollectionPlan(
        pirs=pirs,
        belief_gaps=gaps,
        country=country,
        cycle=cycle,
    )

    if pirs:
        logger.info(
            "[CURIOSITY→PIR] %d VOI-targeted PIRs (signals: %s)",
            len(pirs), [p.signal for p in pirs],
        )

    return plan


__all__ = [
    "SIGNAL_IMPACT",
    "SignalVOI",
    "CuriosityPlan",
    "CuriosityController",
    "compute_signal_voi",
    "curiosity_to_pirs",
]
