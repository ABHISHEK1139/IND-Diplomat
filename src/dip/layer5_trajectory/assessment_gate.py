"""
Layer-5 Assessment Gate — Judgment Authority
=============================================

The council *analyzes*.  The gate *authorizes*.

Port of DIP_8 engine/Layer5_Judgment/assessment_gate.py with exact logic preserved.

Design invariants:
    1. The gate receives a structured AssessmentState — never raw session.
    2. WITHHOLD is the DEFAULT.  The system must EARN the right to conclude.
    3. Every WITHHOLD carries a structured explanation.
    4. The gate never modifies the assessment — only stamps APPROVED or WITHHELD.
    5. Rules are deterministic.  No LLM, no randomness.

WITHHOLD Rules (any one triggers):
    Rule 1  Critical PIRs >= 3         → system itself asked for more intel
    Rule 2  Capability coverage < 0.35  → cannot assess military risk
    Rule 3  Stale military signals      → outdated intel ≠ intelligence
    Rule 4  Analytic confidence < 0.55  → insufficient analytical basis
    Rule 5  Trend escalation detected   → momentum > 0.35 + persistence > 0.8 → min ELEVATED
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Layer5_Judgment.assessment_gate")


# =====================================================================
# AssessmentState — the structured input to the gate
# =====================================================================

@dataclass
class AssessmentState:
    """Everything the gate needs to decide. Populated from finalized session."""

    # Dimension coverages (0.0 – 1.0)
    capability_coverage: float = 0.0
    intent_coverage: float = 0.0
    stability_coverage: float = 0.0
    cost_coverage: float = 0.0

    # PIR counts (Priority Intelligence Requirements)
    critical_pirs: int = 0
    total_pirs: int = 0

    # Signal staleness
    stale_signals: List[str] = field(default_factory=list)
    stale_military_signals: List[str] = field(default_factory=list)

    # Confidence metrics
    analytic_confidence: float = 0.0
    epistemic_confidence: float = 0.0
    sensor_confidence: float = 0.0

    # The proposed assessment (from coordinator synthesis)
    proposed_decision: str = "LOW"

    # Investigation metadata
    investigation_rounds: int = 0
    investigation_closed: bool = False

    # Missing signals for reporting
    missing_signals: List[str] = field(default_factory=list)
    pir_descriptions: List[str] = field(default_factory=list)

    # Temporal trend analysis
    temporal_analysis: Any = None

    # Directed collection evidence — when > 0, gate relaxes thresholds
    directed_beliefs_added: int = 0
    withheld_cycle: int = 0

    # Black Swan override
    black_swan_trigger: bool = False
    black_swan_reasons: List[str] = field(default_factory=list)

    # SRE clamping values
    sre_score: float = 0.0
    trend_bonus: float = 0.0
    deterministic_sre: float = 0.0

    # Temporal momentum/persistence for trend override
    momentum: float = 0.0
    persistence: float = 0.0


# =====================================================================
# GateVerdict — what the gate returns
# =====================================================================

@dataclass
class GateVerdict:
    """The gate's decision: APPROVED or WITHHELD."""

    approved: bool = False
    withheld: bool = True  # DEFAULT: system must earn approval

    # The final decision label
    decision: str = "WITHHELD"

    # Why the gate blocked (empty if approved)
    reasons: List[str] = field(default_factory=list)

    # What collection would unlock the assessment
    required_collection: List[str] = field(default_factory=list)

    # Raw intelligence gaps
    intelligence_gaps: List[str] = field(default_factory=list)

    # Structured collection tasks generated on WITHHELD
    collection_tasks: List[Dict[str, Any]] = field(default_factory=list)

    # If approved, pass through the proposed decision
    proposed_decision: str = ""
    confidence: float = 0.0

    # Black Swan — forced human review
    mandatory_review: bool = False

    # SRE Clamping
    sre_score: float = 0.0
    clamped: bool = False
    clamped_warning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "withheld": self.withheld,
            "decision": self.decision,
            "reasons": list(self.reasons),
            "required_collection": list(self.required_collection),
            "intelligence_gaps": list(self.intelligence_gaps),
            "collection_tasks": list(self.collection_tasks),
            "proposed_decision": self.proposed_decision,
            "confidence": round(self.confidence, 4),
            "mandatory_review": self.mandatory_review,
            "sre_score": round(self.sre_score, 4),
            "clamped": self.clamped,
            "clamped_warning": self.clamped_warning,
        }


# =====================================================================
# Gate Rules — deterministic, no LLM
# =====================================================================

_CRITICAL_PIR_THRESHOLD = 3
_CAPABILITY_COVERAGE_FLOOR = 0.35
_STALENESS_RECENCY_CUTOFF = 0.10
_CONFIDENCE_FLOOR = 0.55
_TREND_MOMENTUM_FLOOR = 0.35
_TREND_PERSISTENCE_FLOOR = 0.8
_STRONG_MOMENTUM_THRESHOLD = 0.50


def _check_critical_pirs(state: AssessmentState) -> Optional[str]:
    """Rule 1: System itself requested collection."""
    if state.critical_pirs >= _CRITICAL_PIR_THRESHOLD:
        return (
            f"System issued {state.critical_pirs} CRITICAL PIRs — "
            f"the system itself declared it needs more intelligence "
            f"before it can conclude."
        )
    return None


def _check_capability_coverage(state: AssessmentState) -> Optional[str]:
    """Rule 2: Military data too weak for escalation assessment."""
    if state.capability_coverage < _CAPABILITY_COVERAGE_FLOOR:
        return (
            f"Capability coverage is {state.capability_coverage:.2f} "
            f"(threshold: {_CAPABILITY_COVERAGE_FLOOR:.2f}) — "
            f"insufficient military intelligence to assess escalation risk."
        )
    return None


def _check_stale_military(state: AssessmentState) -> Optional[str]:
    """Rule 3: Stale military signals invalidate escalation claims."""
    if state.stale_military_signals:
        sigs = ", ".join(state.stale_military_signals[:5])
        return (
            f"Stale military signals detected: {sigs} — "
            f"outdated intelligence cannot support current assessment."
        )
    return None


def _check_confidence(state: AssessmentState) -> Optional[str]:
    """Rule 4: Low analytic confidence → insufficient analytical basis."""
    if state.analytic_confidence < _CONFIDENCE_FLOOR:
        return (
            f"Analytic confidence is {state.analytic_confidence:.3f} "
            f"(threshold: {_CONFIDENCE_FLOOR:.2f}) — "
            f"insufficient analytical basis to conclude."
        )
    return None


def _check_trend_escalation(state: AssessmentState) -> Optional[str]:
    """Rule 5: Escalation patterns detected in temporal trends.

    IF momentum > 0.35 AND persistence > 0.8 for any signal,
    THEN the assessment MUST be at least ELEVATED (not LOW).

    IF momentum > 0.50 (strong), force minimum ELEVATED regardless.
    """
    if state.momentum > _STRONG_MOMENTUM_THRESHOLD and state.persistence > _TREND_PERSISTENCE_FLOOR:
        return (
            f"Strong trend escalation: momentum={state.momentum:.2f} — "
            f"forcing minimum ELEVATED assessment."
        )
    if state.momentum > _TREND_MOMENTUM_FLOOR and state.persistence > _TREND_PERSISTENCE_FLOOR:
        return (
            f"Trend escalation detected: momentum={state.momentum:.2f}, "
            f"persistence={state.persistence:.2f} — "
            f"assessment cannot be LOW with these temporal indicators."
        )
    return None


def _build_collection_tasks(state: AssessmentState, reasons: List[str]) -> List[Dict[str, Any]]:
    """Generate structured collection tasks from WITHHOLD reasons."""
    tasks = []
    for reason in reasons:
        if "PIR" in reason:
            tasks.append({
                "signal": "PIR_resolution",
                "modality": "HUMINT",
                "priority": "CRITICAL",
                "reason": reason,
                "source_hint": "diplomatic_channels",
            })
        elif "capability" in reason.lower():
            tasks.append({
                "signal": "military_capability",
                "modality": "SIGINT",
                "priority": "HIGH",
                "reason": reason,
                "source_hint": "satellite_imagery",
            })
        elif "stale" in reason.lower():
            tasks.append({
                "signal": "military_refresh",
                "modality": "OSINT",
                "priority": "HIGH",
                "reason": reason,
                "source_hint": "gdelt_15min",
            })
        elif "confidence" in reason.lower():
            tasks.append({
                "signal": "corroboration",
                "modality": "MULTI_SOURCE",
                "priority": "MEDIUM",
                "reason": reason,
                "source_hint": "cross_reference",
            })
    return tasks


# =====================================================================
# Main Gate Function
# =====================================================================

def assess(state: AssessmentState) -> GateVerdict:
    """Run all WITHHOLD rules and return a GateVerdict.

    Rules are evaluated in order. First failing rule triggers WITHHOLD.
    Trend escalation (Rule 5) can override LOW → ELEVATED even if no other
    rule fails.
    """
    reasons: List[str] = []
    checks = [
        ("critical_pirs", _check_critical_pirs),
        ("capability_coverage", _check_capability_coverage),
        ("stale_military", _check_stale_military),
        ("confidence", _check_confidence),
    ]

    for check_name, check_fn in checks:
        reason = check_fn(state)
        if reason:
            reasons.append(reason)

    # Rule 5: Trend escalation — can override LOW → ELEVATED
    trend_reason = _check_trend_escalation(state)
    if trend_reason:
        reasons.append(trend_reason)

    # Determine verdict
    if reasons:
        # Check if only trend escalation (no hard WITHHOLD rules)
        hard_reasons = [r for r in reasons if "trend" not in r.lower() and "momentum" not in r.lower()]
        if hard_reasons:
            # Hard WITHHOLD
            tasks = _build_collection_tasks(state, hard_reasons)
            return GateVerdict(
                approved=False,
                withheld=True,
                decision="WITHHELD",
                reasons=hard_reasons,
                required_collection=[r for r in hard_reasons],
                intelligence_gaps=list(state.missing_signals),
                collection_tasks=tasks,
                proposed_decision=state.proposed_decision,
                confidence=state.analytic_confidence,
                mandatory_review=state.black_swan_trigger,
                sre_score=state.sre_score,
            )
        else:
            # Trend-only: override to ELEVATED but still approve
            decision = "ELEVATED" if state.proposed_decision == "LOW" else state.proposed_decision
            return GateVerdict(
                approved=True,
                withheld=False,
                decision=decision,
                reasons=[trend_reason],
                proposed_decision=decision,
                confidence=state.analytic_confidence,
                mandatory_review=state.black_swan_trigger,
                sre_score=state.sre_score,
            )
    else:
        # APPROVED — no rules triggered
        return GateVerdict(
            approved=True,
            withheld=False,
            decision=state.proposed_decision,
            reasons=[],
            proposed_decision=state.proposed_decision,
            confidence=state.analytic_confidence,
            mandatory_review=state.black_swan_trigger,
            sre_score=state.sre_score,
        )


# =====================================================================
# Build AssessmentState from CouncilSession
# =====================================================================

def build_assessment_state(session, result: dict) -> AssessmentState:
    """Populate AssessmentState from a completed CouncilSession and pipeline result."""
    sre = result.get("nextgen_sre") or {}
    bs = result.get("black_swan") or {}

    state = AssessmentState(
        capability_coverage=(sre.get("sre_domains") or {}).get("capability", 0.0),
        intent_coverage=(sre.get("sre_domains") or {}).get("intent", 0.0),
        stability_coverage=(sre.get("sre_domains") or {}).get("stability", 0.0),
        cost_coverage=(sre.get("sre_domains") or {}).get("cost", 0.0),
        analytic_confidence=result.get("verification_score", 0.0) or 0.0,
        sre_score=sre.get("sre_escalation_score", 0.0) or 0.0,
        trend_bonus=(sre.get("sre_input") or {}).get("trend_bonus", 0.0),
        proposed_decision=result.get("threat_level") or "LOW",
        missing_signals=session.missing_signals if hasattr(session, "missing_signals") else [],
        black_swan_trigger=bool(bs.get("triggered", False)),
        black_swan_reasons=bs.get("reasons", []),
    )
    return state
