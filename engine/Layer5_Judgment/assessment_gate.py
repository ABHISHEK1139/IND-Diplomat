"""
Layer-5 Assessment Gate — Judgment Authority
=============================================

The council *analyzes*.  The gate *authorizes*.

This module intercepts the coordinator's synthesized assessment and
decides whether the system is allowed to conclude (LOW / ELEVATED / HIGH)
or must WITHHOLD the assessment because the intelligence basis is
insufficient.

Analogy:  A senior intelligence officer reviewing the analyst's draft
before release.  The analyst can write anything — but it leaves the
building only if the reviewing officer signs off.

Design invariants:
    1. The gate receives a structured AssessmentState — never raw session.
    2. WITHHOLD is the DEFAULT.  The system must EARN the right to conclude.
    3. Every WITHHOLD carries a structured explanation: what is missing,
       what would change the assessment, and what collection is required.
    4. The gate never modifies the assessment — it only stamps
       APPROVED or WITHHELD.
    5. Rules are deterministic.  No LLM, no randomness.

WITHHOLD Rules (any one triggers):
    Rule 1  Critical PIRs >= 3     → system itself asked for more intel
    Rule 2  Capability coverage < 0.35  → cannot assess military risk
    Rule 3  Stale military signals  → outdated intel ≠ intelligence
    Rule 4  Analytic confidence < 0.55  → insufficient analytical basis
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
    """
    Everything the gate needs to decide.

    Populated by the coordinator from the finalized session.
    Every field maps to something the system already computes.
    """
    # Dimension coverages (0.0 – 1.0)
    capability_coverage: float = 0.0
    intent_coverage: float = 0.0
    stability_coverage: float = 0.0
    cost_coverage: float = 0.0

    # PIR counts
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

    # Temporal trend analysis (from TemporalMemory)
    temporal_analysis: Any = None

    # Directed collection evidence (STEP 6 — learning rule)
    # Set by coordinator when directed collection adds new beliefs.
    # When > 0, the gate relaxes thresholds to allow reassessment.
    directed_beliefs_added: int = 0
    withheld_cycle: int = 0

    # Phase 5.2: Black Swan override
    black_swan_trigger: bool = False
    black_swan_reasons: List[str] = field(default_factory=list)


# =====================================================================
# GateVerdict — what the gate returns
# =====================================================================

@dataclass
class GateVerdict:
    """
    The gate's decision: APPROVED or WITHHELD.

    If WITHHELD, the verdict carries:
        - reasons: why the assessment was blocked
        - required_collection: what intelligence is needed
        - intelligence_gaps: which signals are missing
    """
    approved: bool = False
    withheld: bool = True  # default: the system must earn approval

    # The final decision label emitted to the user
    decision: str = "WITHHELD"

    # Why the gate blocked (empty if approved)
    reasons: List[str] = field(default_factory=list)

    # What collection would unlock the assessment
    required_collection: List[str] = field(default_factory=list)

    # Raw intelligence gaps
    intelligence_gaps: List[str] = field(default_factory=list)

    # Structured collection tasks generated on WITHHELD
    # Each dict: {signal, modality, priority, reason, source_hint}
    collection_tasks: List[Dict[str, Any]] = field(default_factory=list)

    # If approved, pass through the proposed decision
    proposed_decision: str = ""
    confidence: float = 0.0

    # Phase 5.2: Black Swan — forced human review
    mandatory_review: bool = False

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
        }


# =====================================================================
# Gate Rules — deterministic, no LLM
# =====================================================================

# Thresholds (tunable but not AI-generated)
_CRITICAL_PIR_THRESHOLD = 3
_CAPABILITY_COVERAGE_FLOOR = 0.35
_STALENESS_RECENCY_CUTOFF = 0.10     # recency < 0.10 = stale data
_CONFIDENCE_FLOOR = 0.55


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


# ── Rule 5: Trend override ────────────────────────────────────────
# Phase 8: tightened momentum thresholds from 0.22/0.6 to 0.35/0.8.
# Added strong-trend override: momentum > 0.50 AND persistence > 2.0
# forces minimum ELEVATED regardless of other factors.
_TREND_MOMENTUM_FLOOR = 0.35          # Phase 8: was 0.22
_TREND_PERSISTENCE_FLOOR = 0.8        # Phase 8: was 0.6
_STRONG_MOMENTUM_THRESHOLD = 0.50     # Phase 8: new
_STRONG_PERSISTENCE_THRESHOLD = 2.0   # Phase 8: new


def _check_trend_escalation(state: AssessmentState) -> Optional[str]:
    """Rule 5: Escalation patterns detected in temporal trends.

    IF momentum > 0.35 AND persistence > 0.8 for any signal,
    THEN the assessment MUST be at least MEDIUM (not LOW).

    Phase 8 addition: IF momentum > 0.50 AND persistence > 2.0,
    force minimum ELEVATED regardless of other factors.

    This rule only triggers when the proposed decision is LOW but
    temporal trends say otherwise — wars are predicted by buildup,
    not current state.  A LOW assessment contradicts escalation trends.
    """
    trend_data = getattr(state, "temporal_analysis", None)
    if trend_data is None:
        return None

    # Only override LOW assessments
    if state.proposed_decision.upper() not in ("LOW", "MINIMAL", "NEGLIGIBLE"):
        return None

    trend_overrides = getattr(trend_data, "trend_overrides", []) or []
    if not trend_overrides:
        return None

    # Get details for the log
    details = []
    indicators = getattr(trend_data, "indicators", {}) or {}
    for sig in trend_overrides[:3]:
        ind = indicators.get(sig)
        if ind:
            details.append(
                f"{sig}(momentum=+{ind.momentum:.2f}, "
                f"persistence={ind.persistence:.2f})"
            )

    return (
        f"[TREND OVERRIDE] Proposed decision is {state.proposed_decision} "
        f"but temporal analysis detected escalation patterns in "
        f"{len(trend_overrides)} signal(s): {', '.join(details)}. "
        f"Rising trends with sustained persistence contradict a LOW assessment."
    )


# Ordered rule list — each returns a reason string or None.
_RULES = [
    ("critical_pirs", _check_critical_pirs),
    ("capability_coverage", _check_capability_coverage),
    ("stale_military", _check_stale_military),
    ("confidence", _check_confidence),
    ("trend_escalation", _check_trend_escalation),
]


# =====================================================================
# evaluate() — the single entry point
# =====================================================================

def evaluate(state: AssessmentState) -> GateVerdict:
    """
    Evaluate whether the system is authorized to release its assessment.

    Returns GateVerdict:
        approved=True   → verdict.decision = the proposed assessment
        approved=False  → verdict.decision = "WITHHELD" with reasons

    The coordinator calls this AFTER _synthesize_decision() but BEFORE
    generating the final report.
    """
    reasons: List[str] = []

    # ── Phase 5.2: Black Swan override ─────────────────────────
    # Black Swan cannot be WITHHELD.  Force APPROVED with capped
    # confidence and mandatory human review.
    if state.black_swan_trigger:
        logger.warning(
            "[GATE] BLACK SWAN override — forcing APPROVED with "
            "capped confidence and mandatory human review.  "
            "Reasons: %s", state.black_swan_reasons,
        )
        capped_conf = min(state.analytic_confidence, 0.60)
        return GateVerdict(
            approved=True,
            withheld=False,
            decision=state.proposed_decision,
            reasons=[f"BLACK SWAN OVERRIDE: {r}" for r in state.black_swan_reasons],
            required_collection=[],
            intelligence_gaps=[],
            proposed_decision=state.proposed_decision,
            confidence=capped_conf,
            mandatory_review=True,
        )

    # ── Learning rule: relax thresholds if directed collection
    #    added new evidence (prevents infinite WITHHELD loop) ──
    #    After cycle 2+, if new beliefs were promoted, relax
    #    capability_coverage and confidence floors by 20%.
    _evidence_relaxation = False
    if state.withheld_cycle >= 2 and state.directed_beliefs_added > 0:
        _evidence_relaxation = True
        logger.info(
            "[GATE] Learning rule: directed collection added %d beliefs "
            "across %d cycles — relaxing thresholds for reassessment",
            state.directed_beliefs_added, state.withheld_cycle,
        )

    for rule_name, rule_fn in _RULES:
        reason = rule_fn(state)
        if reason:
            # If evidence relaxation is active, skip coverage & confidence
            # rules — they were the original blockers and new evidence
            # may have shifted the picture enough to allow assessment.
            if _evidence_relaxation and rule_name in ("capability_coverage", "confidence"):
                logger.info(
                    "[GATE] Rule '%s' RELAXED due to directed collection evidence",
                    rule_name,
                )
                continue
            reasons.append(reason)
            logger.info("[GATE] WITHHOLD triggered by %s: %s", rule_name, reason)

    # ── Map Intelligence Gaps into Actionable Intelligence ──────────────────────────
    actionable_gaps = []
    
    # Check what PIRs or missing signals are currently causing trouble.
    # Map their keywords into clear intelligence directives instead of raw variable names.
    missing_elements = state.pir_descriptions + state.missing_signals
    if not missing_elements and reasons:
        # Fall back to using the reasons to deduce gaps
        missing_elements = reasons

    for gap in missing_elements:
        gap_upper = gap.upper()
        if "ECO_PRESSURE" in gap_upper or "SANCTIONS" in gap_upper:
            actionable_gaps.append(f"Missing confirmation of: sanction severity escalation ({gap[:40]})")
        elif "NEGOTIATION" in gap_upper or "COERCIVE_BARGAINING" in gap_upper:
            actionable_gaps.append(f"Missing confirmation of: formal negotiation collapse timeline ({gap[:40]})")
        elif "MIL_ESCALATION" in gap_upper or "FORCE_POSTURE" in gap_upper or "MOBILIZATION" in gap_upper or "CAPABILITY" in gap_upper:
            actionable_gaps.append(f"Missing confirmation of: military capability posture validation ({gap[:40]})")
        elif "ALLIANCE" in gap_upper:
            actionable_gaps.append(f"Missing confirmation of: security alliance/treaty activation triggers ({gap[:40]})")
        elif "WMD" in gap_upper:
            actionable_gaps.append(f"Missing confirmation of: strategic WMD capability movement ({gap[:40]}) - Requires multi-source validation")
        else:
            actionable_gaps.append(f"Missing confirmation of: {gap[:60]}")
            
    # Deduplicate Actionable gaps
    actionable_gaps = list(set(actionable_gaps))

    if not reasons:
        # All rules passed — assessment is authorized.
        logger.info(
            "[GATE] Assessment APPROVED — decision=%s, confidence=%.3f",
            state.proposed_decision, state.analytic_confidence,
        )
        return GateVerdict(
            approved=True,
            withheld=False,
            decision=state.proposed_decision,
            reasons=[],
            required_collection=[],
            intelligence_gaps=actionable_gaps,
            proposed_decision=state.proposed_decision,
            confidence=state.analytic_confidence,
        )

    # ── WITHHELD ──────────────────────────────────────────────────
    # Build required_collection from PIR descriptions and missing signals.
    required = []
    for desc in state.pir_descriptions:
        if desc not in required:
            required.append(desc)
    for sig in state.missing_signals:
        entry = f"Missing: {sig}"
        if entry not in required:
            required.append(entry)
    for sig in state.stale_military_signals:
        entry = f"Stale: {sig} — current data required"
        if entry not in required:
            required.append(entry)

    # ── Auto-generate structured collection tasks ─────────────────
    # These give downstream consumers (pipeline, World Monitor) a
    # machine-readable manifest of what to collect next.
    import re as _re
    collection_tasks: List[Dict[str, Any]] = []
    _seen_tasks: set = set()

    # 1. Missing signals → OSINT collection tasks
    for sig in state.missing_signals:
        sig_upper = str(sig).strip().upper()
        if sig_upper.startswith("SIG_") and sig_upper not in _seen_tasks:
            _seen_tasks.add(sig_upper)
            collection_tasks.append({
                "signal": sig_upper,
                "modality": "OSINT",
                "priority": "HIGH",
                "reason": f"Gate WITHHELD — signal absent: {sig_upper}",
                "source_hint": "GDELT_OR_WORLD_MONITOR",
            })

    # 2. Stale military signals → REFRESH collection tasks (highest priority)
    for sig in state.stale_military_signals:
        sig_upper = str(sig).strip().upper()
        if sig_upper not in _seen_tasks:
            _seen_tasks.add(sig_upper)
            collection_tasks.append({
                "signal": sig_upper,
                "modality": "OSINT",
                "priority": "CRITICAL",
                "reason": f"Gate WITHHELD — stale military data: {sig_upper}",
                "source_hint": "GDELT_REFRESH",
            })

    # 3. Extract signals from PIR text descriptions (fallback)
    for pir_text in state.pir_descriptions:
        sig_match = _re.search(r"(SIG_[A-Z_]+)", str(pir_text))
        if sig_match:
            sig_upper = sig_match.group(1)
            if sig_upper not in _seen_tasks:
                _seen_tasks.add(sig_upper)
                collection_tasks.append({
                    "signal": sig_upper,
                    "modality": "OSINT",
                    "priority": "HIGH",
                    "reason": str(pir_text)[:200],
                    "source_hint": "PIR_DERIVED",
                })

    # 4. If low capability coverage, request broad military sweep + OSINT sweep
    if state.capability_coverage < _CAPABILITY_COVERAGE_FLOOR:
        sweep_sig = "SIG_MIL_ESCALATION"
        if sweep_sig not in _seen_tasks:
            _seen_tasks.add(sweep_sig)
            collection_tasks.append({
                "signal": sweep_sig,
                "modality": "WORLD_MONITOR_SWEEP",
                "priority": "CRITICAL",
                "reason": f"Capability coverage {state.capability_coverage:.2f} < {_CAPABILITY_COVERAGE_FLOOR} — broad military sweep required",
                "source_hint": "WORLD_MONITOR",
            })
        osint_sig = "SIG_FORCE_POSTURE"
        if osint_sig not in _seen_tasks:
            _seen_tasks.add(osint_sig)
            collection_tasks.append({
                "signal": osint_sig,
                "modality": "OSINT_SWEEP",
                "priority": "HIGH",
                "reason": f"Capability coverage {state.capability_coverage:.2f} — expand OSINT perception",
                "source_hint": "MOLTBOT",
            })

    logger.info(
        "[GATE] Assessment WITHHELD — %d rules triggered, %d collection tasks generated, proposed=%s, confidence=%.3f",
        len(reasons), len(collection_tasks), state.proposed_decision, state.analytic_confidence,
    )

    return GateVerdict(
        approved=False,
        withheld=True,
        decision="WITHHELD",
        reasons=reasons,
        required_collection=required[:15],
        intelligence_gaps=actionable_gaps,
        collection_tasks=collection_tasks[:20],
        proposed_decision=state.proposed_decision,
        confidence=state.analytic_confidence,
    )


# =====================================================================
# Helper: build AssessmentState from coordinator session
# =====================================================================

def build_assessment_state(session: Any) -> AssessmentState:
    """
    Extract AssessmentState from a finalized CouncilSession.

    This is the ONLY place that reads session internals for the gate.
    The gate itself operates on the structured AssessmentState only.
    """
    # Dimension coverages from hypotheses (legacy path)
    dimensions = {"CAPABILITY": 0.0, "INTENT": 0.0, "STABILITY": 0.0, "COST": 0.0}
    dim_map = {
        "security": "CAPABILITY",
        "economic": "COST",
        "domestic": "STABILITY",
        "diplomatic": "INTENT",
    }
    for h in list(getattr(session, "hypotheses", []) or []):
        minister = str(getattr(h, "minister", "") or "").lower()
        dim = None
        for key, val in dim_map.items():
            if key in minister:
                dim = val
                break
        if dim is None:
            dim = str(getattr(h, "dimension", "UNKNOWN") or "UNKNOWN").upper()
        coverage = max(0.0, min(1.0, float(getattr(h, "coverage", 0.0) or 0.0)))
        if dim in dimensions:
            dimensions[dim] = max(dimensions[dim], coverage)

    # Primary path: use synthesized state-domain indices when available.
    # This keeps the gate aligned with the actual SRE/state engine instead of
    # depending only on minister hypothesis coverage.
    state_ctx = getattr(session, "state_context", None)
    try:
        state_dims = {
            "CAPABILITY": float(getattr(state_ctx, "capability_index", 0.0) or 0.0),
            "INTENT": float(getattr(state_ctx, "intent_index", 0.0) or 0.0),
            "STABILITY": float(getattr(state_ctx, "stability_index", 0.0) or 0.0),
            "COST": float(getattr(state_ctx, "cost_index", 0.0) or 0.0),
        }
    except Exception:
        state_dims = {}
    for key, value in state_dims.items():
        dimensions[key] = max(dimensions[key], max(0.0, min(1.0, float(value or 0.0))))

    # Secondary path: if SRE domains are populated, use them as additional
    # evidence for gate dimensions.
    sre_domains = dict(getattr(session, "sre_domains", {}) or {})
    if sre_domains:
        dimensions["CAPABILITY"] = max(dimensions["CAPABILITY"], max(0.0, min(1.0, float(sre_domains.get("capability", 0.0) or 0.0))))
        dimensions["INTENT"] = max(dimensions["INTENT"], max(0.0, min(1.0, float(sre_domains.get("intent", 0.0) or 0.0))))
        dimensions["STABILITY"] = max(dimensions["STABILITY"], max(0.0, min(1.0, float(sre_domains.get("stability", 0.0) or 0.0))))
        dimensions["COST"] = max(dimensions["COST"], max(0.0, min(1.0, float(sre_domains.get("cost", 0.0) or 0.0))))

    # PIR counts
    collection_plan = getattr(session, "collection_plan", None)
    critical_pirs = 0
    total_pirs = 0
    pir_descriptions: List[str] = []
    if collection_plan and hasattr(collection_plan, "pirs"):
        total_pirs = len(collection_plan.pirs)
        for pir in collection_plan.pirs:
            priority = str(getattr(pir, "priority", "") or "")
            if hasattr(priority, "value"):
                priority = priority.value
            if priority == "CRITICAL":
                critical_pirs += 1
            # Build human-readable PIR descriptions
            modality = getattr(pir, "collection", "")
            if hasattr(modality, "value"):
                modality = modality.value
            pir_descriptions.append(
                f"{getattr(pir, 'signal', '?')} via {modality} "
                f"[{priority}] — {getattr(pir, 'reason', '')[:120]}"
            )

    # Stale military signals (recency < threshold)
    stale_military = []
    stale_all = []
    military_signals = {
        "SIG_MIL_ESCALATION", "SIG_FORCE_POSTURE", "SIG_MIL_MOBILIZATION",
        "SIG_LOGISTICS_PREP", "SIG_LOGISTICS_SURGE", "SIG_WMD_RISK",
    }
    projected = getattr(getattr(session, "state_context", None), "projected_signals", {}) or {}
    for sig_name, proj in projected.items():
        recency = float(getattr(proj, "recency", 1.0) or 1.0)
        if recency < _STALENESS_RECENCY_CUTOFF:
            stale_all.append(sig_name)
            if sig_name.upper() in military_signals:
                stale_military.append(sig_name)

    # Missing signals
    missing = list(getattr(session, "missing_signals", []) or [])

    # ── Temporal trend analysis ───────────────────────────────────
    temporal_analysis = None
    try:
        from engine.Layer3_StateModel.temporal_memory import analyze_trends
        sc = getattr(session, "state_context", None)
        current_beliefs = {}
        if sc:
            sig_conf = getattr(sc, "signal_confidence", {}) or {}
            current_beliefs = {k: float(v) for k, v in sig_conf.items() if float(v) > 0}
        temporal_analysis = analyze_trends(current_beliefs)
        if temporal_analysis and temporal_analysis.escalation_pattern:
            logger.info(
                "[GATE] Temporal analysis: %d escalation pattern(s) detected",
                len(temporal_analysis.trend_overrides),
            )
    except Exception as e:
        logger.debug("Temporal analysis unavailable: %s", e)

    return AssessmentState(
        capability_coverage=dimensions["CAPABILITY"],
        intent_coverage=dimensions["INTENT"],
        stability_coverage=dimensions["STABILITY"],
        cost_coverage=dimensions["COST"],
        critical_pirs=critical_pirs,
        total_pirs=total_pirs,
        stale_signals=stale_all,
        stale_military_signals=stale_military,
        analytic_confidence=float(getattr(session, "final_confidence", 0.0) or 0.0),
        epistemic_confidence=float(getattr(session, "epistemic_confidence", 0.0) or 0.0),
        sensor_confidence=float(getattr(session, "sensor_confidence", 0.0) or 0.0),
        proposed_decision=str(getattr(session, "king_decision", "LOW") or "LOW"),
        investigation_rounds=int(getattr(session, "investigation_rounds", 0) or 0),
        investigation_closed=bool(getattr(session, "investigation_closed", False)),
        missing_signals=missing,
        pir_descriptions=pir_descriptions,
        temporal_analysis=temporal_analysis,
        black_swan_trigger=bool(
            getattr(getattr(session, "black_swan_result", None), "triggered", False)
        ),
        black_swan_reasons=list(
            getattr(getattr(session, "black_swan_result", None), "reasons", []) or []
        ),
    )


__all__ = [
    "AssessmentState",
    "GateVerdict",
    "evaluate",
    "build_assessment_state",
]
