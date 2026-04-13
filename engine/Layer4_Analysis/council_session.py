"""
The Council Session.
Shared memory object for the deliberative reasoning process.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime, timezone

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.schema import AssessmentReport, Hypothesis
from engine.Layer4_Analysis.reasoning_phase import ReasoningPhase

class SessionStatus(Enum):
    OPEN = "OPEN"
    DELIBERATING = "DELIBERATING"
    INVESTIGATING = "INVESTIGATING"
    CONCLUDED = "CONCLUDED"
    FAILED = "FAILED"

@dataclass
class MinisterReport:
    minister_name: str
    predicted_signals: List[str]
    confidence: float
    classification_source: str = "llm"
    reasoning_source: str = "pending"
    classification_degraded: bool = False
    reasoning_degraded: bool = False
    degradation_reasons: List[str] = field(default_factory=list)
    # ── Reasoning pass fields (populated by reason()) ────────────
    risk_level_adjustment: str = "maintain"     # "increase" / "decrease" / "maintain"
    primary_drivers: List[str] = field(default_factory=list)
    critical_gaps: List[str] = field(default_factory=list)
    counterarguments: List[str] = field(default_factory=list)
    confidence_modifier: float = 0.0            # suggested adjustment [-0.10 .. +0.10]
    reasoning_text: str = ""                    # raw LLM reasoning for red team
    effort_level: str = "medium"
    justification_strength: float = 0.5
    self_critique_applied: bool = False
    self_critique_issues: List[str] = field(default_factory=list)
    reasoning_quality_score: float = 0.0
    reasoning_signal_density: float = 0.0
    reasoning_length_ratio: float = 0.0
    overthinking_detected: bool = False
    underthinking_detected: bool = False
    reasoning_monitor_issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "minister_name": self.minister_name,
            "predicted_signals": list(self.predicted_signals),
            "confidence": round(self.confidence, 4),
            "classification_source": self.classification_source,
            "reasoning_source": self.reasoning_source,
            "classification_degraded": bool(self.classification_degraded),
            "reasoning_degraded": bool(self.reasoning_degraded),
            "degradation_reasons": list(self.degradation_reasons),
            "risk_level_adjustment": self.risk_level_adjustment,
            "primary_drivers": list(self.primary_drivers),
            "critical_gaps": list(self.critical_gaps),
            "counterarguments": list(self.counterarguments),
            "confidence_modifier": round(self.confidence_modifier, 4),
            "effort_level": self.effort_level,
            "justification_strength": round(self.justification_strength, 4),
            "self_critique_applied": bool(self.self_critique_applied),
            "self_critique_issues": list(self.self_critique_issues),
            "reasoning_quality_score": round(self.reasoning_quality_score, 4),
            "reasoning_signal_density": round(self.reasoning_signal_density, 4),
            "reasoning_length_ratio": round(self.reasoning_length_ratio, 4),
            "overthinking_detected": bool(self.overthinking_detected),
            "underthinking_detected": bool(self.underthinking_detected),
            "reasoning_monitor_issues": list(self.reasoning_monitor_issues),
        }

    def has_substantive_reasoning(self) -> bool:
        return bool(
            (self.primary_drivers or self.critical_gaps or self.counterarguments)
            and str(self.reasoning_source or "").lower() == "llm"
            and not self.reasoning_degraded
        )


@dataclass
class FullContext:
    """
    Frozen snapshot of full system state passed to all ministers
    during the reasoning pass.  Every minister sees the same object
    so no information asymmetry except their system-prompt bias.
    """
    pressures: Dict[str, float] = field(default_factory=dict)
    projected_signals: Dict[str, Any] = field(default_factory=dict)
    trajectory: Dict[str, float] = field(default_factory=dict)
    state_probabilities: Dict[str, float] = field(default_factory=dict)
    gaps: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    escalation_score: float = 0.0
    trend_patterns: Dict[str, Any] = field(default_factory=dict)
    signal_confidence: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pressures": dict(self.pressures),
            "trajectory": dict(self.trajectory),
            "state_probabilities": {k: round(v, 4) for k, v in self.state_probabilities.items()},
            "gaps": list(self.gaps),
            "contradictions": list(self.contradictions),
            "escalation_score": round(self.escalation_score, 4),
            "signal_confidence": {k: round(v, 3) for k, v in self.signal_confidence.items()},
        }

@dataclass
class CouncilSession:
    """
    The shared state of a Layer-4 reasoning session.
    
    All modules (Red Team, CRAG, CoVe, Verifier, Refusal Engine, HITL)
    interact ONLY through this object. No direct module-to-module calls.
    """
    session_id: str
    question: str
    state_context: StateContext
    
    # DELIBERATION STAGE: Ministers propose hypotheses
    ministers_reports: List[MinisterReport] = field(default_factory=list)
    hypotheses: List[Hypothesis] = field(default_factory=list)
    
    # DEBATE STAGE: Conflicts and red team analysis
    identified_conflicts: List[str] = field(default_factory=list)
    red_team_report: Optional[Dict[str, Any]] = None
    
    # INVESTIGATION STAGE: Missing signals and evidence
    missing_signals: List[str] = field(default_factory=list)
    evidence_log: List[str] = field(default_factory=list)
    
    # DECISION STAGE: Final assessment
    king_decision: Optional[str] = None
    final_decision: Optional[str] = None
    assessment_report: Optional[AssessmentReport] = None
    final_confidence: float = 0.0
    verification_score: float = 0.0
    logic_score: float = 0.0
    strategic_status: str = "stable"
    sensor_confidence: float = 0.0
    document_confidence: float = 0.0
    driver_score: float = 0.0
    constraint_score: float = 0.0
    net_escalation: float = 0.0
    evidence_atom_count: int = 0
    grounding_passed: bool = False
    claim_support_passed: bool = False
    required_atoms_for_decision: int = 0
    epistemic_confidence: float = 0.0
    evidence_atoms: List[Any] = field(default_factory=list)
    low_confidence_assessment: bool = False
    early_warning_index: float = 0.0
    escalation_sync: float = 0.0
    prewar_detected: bool = False
    warning: str = ""
    temporal_trend: Dict[str, float] = field(default_factory=dict)
    pressures: Dict[str, float] = field(default_factory=dict)
    investigation_needs: List[str] = field(default_factory=list)
    collection_plan: Any = None  # Core.intelligence.pir.CollectionPlan — typed PIR-based collection plan
    investigation_rounds: int = 0
    MAX_INVESTIGATION_ROUNDS: int = 3
    investigation_cycles: int = 0
    MAX_INVESTIGATION_CYCLES: int = 3
    investigation_closed: bool = False
    last_investigated_signal_set: List[str] = field(default_factory=list)
    last_investigation_state_signature: str = ""
    last_investigation_material_change: bool = False
    
    # COUNCIL REASONING (two-round deliberation)
    full_context: Optional[Any] = None          # FullContext snapshot
    round1_reports: List[MinisterReport] = field(default_factory=list)
    round2_reports: List[MinisterReport] = field(default_factory=list)
    synthesis_summary: str = ""
    groupthink_flag: bool = False
    groupthink_penalty: float = 0.0
    groupthink_investigation_needed: bool = False
    groupthink_reinvestigated: bool = False
    groupthink_context_gaps: List[str] = field(default_factory=list)
    groupthink_reason: str = ""
    council_adjustment: float = 0.0             # aggregated vote-weighted adjustment
    
    # META
    status: SessionStatus = SessionStatus.OPEN
    turn_count: int = 0
    loop_count: int = 0
    phase: ReasoningPhase = ReasoningPhase.INITIAL_DELIBERATION
    phase_history: List[str] = field(
        default_factory=lambda: [ReasoningPhase.INITIAL_DELIBERATION.value]
    )
    black_swan: bool = False
    allow_prediction: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def add_report(self, report: MinisterReport):
        self.ministers_reports.append(report)
        
    def add_hypothesis(self, hypothesis: Hypothesis):
        self.hypotheses.append(hypothesis)
        
    def get_best_hypothesis(self) -> Optional[MinisterReport]:
        if not self.ministers_reports: return None
        return max(self.ministers_reports, key=lambda x: x.confidence)

    def transition_to(self, phase: ReasoningPhase):
        self.phase = phase
        phase_name = phase.value
        if not self.phase_history or self.phase_history[-1] != phase_name:
            self.phase_history.append(phase_name)

    def summary(self) -> str:
        return (
            f"Session {self.session_id} [{self.status.value}]\n"
            f"Q: {self.question}\n"
            f"Phase: {self.phase.value} | Loops: {self.loop_count}\n"
            f"Hypotheses: {len(self.hypotheses)} | Reports: {len(self.ministers_reports)} | Best Conf: {self.final_confidence:.2f}"
        )
