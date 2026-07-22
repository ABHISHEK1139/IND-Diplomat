"""
IND-Diplomat (dip 2.0) — Core Schema Definitions
=================================================

Every object that flows between layers is defined here.
Strict Pydantic models enforce the boundary contracts that prevent
Layer-4 from ever bypassing the World Model.

Layer Flow:
    RawObservation (L1) → Signal (L2) → Belief (L3) → StateContext (L3)
    → Hypothesis (L4) → AssessmentDecision (L4) → TrajectoryForecast (L5)
    → IntelligenceReport (L6)
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional
from datetime import datetime


# =====================================================================
# Layer 0 — Investigation Engine (DIP 3.0 Foundation)
# =====================================================================
# The Investigation is the ROOT OBJECT of the entire system.
# Every signal, hypothesis, forecast, and report belongs to an Investigation.
# =====================================================================

# --- State Machine ---
INVESTIGATION_STATES = [
    "CREATED",
    "PLANNING",
    "COLLECTING",
    "ANALYZING",
    "REASONING",
    "FORECASTING",
    "REPORTING",
    "MONITORING",
    "ARCHIVED",
]

VALID_TRANSITIONS = {
    "CREATED":      ["PLANNING"],
    "PLANNING":     ["COLLECTING"],
    "COLLECTING":   ["ANALYZING"],
    "ANALYZING":    ["REASONING"],
    "REASONING":    ["FORECASTING"],
    "FORECASTING":  ["REPORTING"],
    "REPORTING":    ["MONITORING", "ARCHIVED"],
    "MONITORING":   ["COLLECTING", "ARCHIVED"],  # Can re-collect for updates
    "ARCHIVED":     ["COLLECTING"],              # Can reopen
}


class UserObjective(BaseModel):
    """WHY the user is investigating. Drives every downstream decision."""
    objective: str                                   # The core question
    decision_support_type: str = "General"           # Government Policy, Business Strategy, Academic Research, Risk Assessment
    time_horizon: str = "Unknown"                    # "10 Years", "6 Months", "30 Days"
    depth: str = "Standard"                          # Quick, Standard, Research, Comprehensive
    output_format: str = "Dossier"                   # Briefing, Dossier, Report, Dashboard
    confidence_target: float = 0.90                  # Minimum acceptable confidence


class InvestigationScope(BaseModel):
    """WHAT the investigation covers. Auto-extracted by the planner."""
    countries: List[str] = Field(default_factory=list)
    domains: List[str] = Field(default_factory=list)
    companies: List[str] = Field(default_factory=list)
    government_bodies: List[str] = Field(default_factory=list)
    key_actors: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)


class CollectionNeed(BaseModel):
    """A single data source requirement within the collection plan."""
    source_type: str                                 # "Government Reports", "News", "Patent Data", etc.
    priority: str = "Medium"                         # Critical, High, Medium, Low
    status: str = "Pending"                          # Pending, Collected, Failed, Skipped
    description: str = ""
    assigned_sensor: Optional[str] = None            # Which sensor/feed handles this


class CollectionPlan(BaseModel):
    """HOW to collect intelligence. Generated from objective + scope."""
    needs: List[CollectionNeed] = Field(default_factory=list)
    generated_at: str = ""
    total_sources_planned: int = 0


class TimelineEvent(BaseModel):
    """An immutable log entry in the investigation timeline."""
    timestamp: str
    event_type: str                                  # STATE_CHANGE, DATA_COLLECTED, ANALYSIS_COMPLETE, ERROR, HITL_REVIEW, ALERT
    description: str
    layer: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InvestigationAlert(BaseModel):
    """A triggered notification within an investigation."""
    alert_id: str
    alert_type: str                                  # CONTRADICTION, NEW_EVIDENCE, CONFIDENCE_DROP, SCOPE_EXPANSION
    message: str
    severity: str = "INFO"                           # INFO, WARNING, CRITICAL
    timestamp: str
    acknowledged: bool = False


class ReasoningTrace(BaseModel):
    """Captures the exact inputs and outputs of a single LLM reasoning step for future training."""
    trace_id: str
    layer: str
    model_used: str
    prompt: str
    context: str
    output: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost: float
    timestamp: str


class HITLFeedback(BaseModel):
    """Human-in-the-Loop review data for DPO training and RLHF."""
    feedback_id: str
    layer: str
    original_data: str
    corrected_data: str
    action_taken: str                                # "Approved", "Rejected", "Edited"
    human_rationale: Optional[str] = None
    timestamp: str


class Investigation(BaseModel):
    """
    The ROOT OBJECT of DIP 3.0.

    Every signal, hypothesis, forecast, report, and human correction
    belongs to an Investigation. This is the atomic unit of the platform.

    Lifecycle: CREATED → PLANNING → COLLECTING → ANALYZING → REASONING
               → FORECASTING → REPORTING → MONITORING → ARCHIVED
    """
    # --- Identity ---
    investigation_id: str
    title: str
    description: str = ""
    original_query: str
    owner: str = "default"
    priority: str = "Medium"                         # Low, Medium, High, Critical
    visibility: str = "Private"                      # Private, Team, Public
    tags: List[str] = Field(default_factory=list)
    version: int = 1

    # --- State Machine ---
    status: str = "CREATED"

    # --- Core Structure ---
    objective: UserObjective
    scope: InvestigationScope = Field(default_factory=InvestigationScope)
    collection_plan: CollectionPlan = Field(default_factory=CollectionPlan)

    # --- Timestamps ---
    created_at: str
    updated_at: str

    # --- Evidence & Analysis References ---
    evidence_count: int = 0                          # Total raw observations collected
    signal_count: int = 0                            # Structured signals extracted
    hypothesis_count: int = 0                        # Expert hypotheses generated
    reports_generated: int = 0
    world_model_id: Optional[str] = None

    # --- SEIL (Self-Evolving Intelligence Loop) ---
    reasoning_traces: List[ReasoningTrace] = Field(default_factory=list)
    human_feedback: List[HITLFeedback] = Field(default_factory=list)
    alerts: List[InvestigationAlert] = Field(default_factory=list)

    # --- Backward Compatibility ---
    @property
    def goal(self) -> "InvestigationGoal":
        """Backward-compatible accessor for legacy code that references inv.goal."""
        return InvestigationGoal(
            topic=self.title,
            target_country=self.scope.countries[0] if self.scope.countries else None,
            time_horizon=self.objective.time_horizon,
            domains=self.scope.domains,
            investigation_goal=self.objective.objective,
            confidence_target=self.objective.confidence_target,
            required_sources=[n.source_type for n in self.collection_plan.needs],
        )


class InvestigationGoal(BaseModel):
    """Legacy goal model — kept for backward compatibility with Layer 1-9 code."""
    topic: str
    target_country: Optional[str] = None
    time_horizon: str
    domains: List[str]
    investigation_goal: str
    confidence_target: float = 0.90
    required_sources: List[str] = Field(default_factory=list)

# =====================================================================
# Layer 1 — Collection
# =====================================================================

class SourceProfile(BaseModel):
    """Profile of a collection source tracking reliability and bias."""
    source_id: str
    reliability_score: float = 0.5
    bias_score: float = 0.0
    historical_accuracy: float = 0.5
    used_count: int = 0
    rejected_count: int = 0

class RawObservation(BaseModel):
    """Layer 1 output: Raw data observed from the world."""
    source_id: str
    source_type: str = "OSINT"          # GDELT, OSINT, NEWS, GOV, SENSOR
    content: str
    timestamp: str
    country: Optional[str] = None
    goldstein_score: Optional[float] = None   # GDELT Goldstein scale
    cameo_code: Optional[str] = None          # CAMEO event code


# =====================================================================
# Layer 2 — Knowledge (Expanded for DIP 3.0)
# =====================================================================

class Entity(BaseModel):
    """A tracked actor, organization, or location."""
    entity_id: str
    name: str
    type: str
    attributes: Dict[str, Any] = Field(default_factory=dict)

class Claim(BaseModel):
    """A testable assertion extracted from text."""
    claim_id: str
    subject: str
    predicate: str
    object: str
    confidence: float
    source_ref: str

class Signal(BaseModel):
    """Layer 2 output: Structured extraction from raw observations."""
    entity: str
    action: str                                # Canonical SIG_* code
    target: Optional[str] = None
    intensity: float                           # 0.0–1.0 normalized
    confidence: float                          # 0.0–1.0 source reliability
    source_ref: str
    domain: str = "unknown"                    # military, diplomatic, economic, internal
    timestamp: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    reliability_score: float = 0.5
    verification_status: str = "Unverified"
    weight: float = 1.0


# =====================================================================
# Layer 3 — State Model
# =====================================================================

class Belief(BaseModel):
    """Layer 3 intermediate: A corroborated observation promoted to belief."""
    signal_code: str
    support_score: float                       # Corroboration strength
    belief_level: str = "weak"                 # ignore, weak, moderate, strong
    source_count: int = 1                      # Independent sources
    recency_weight: float = 1.0                # Exponential decay
    source_types: List[str] = Field(default_factory=list)


class TemporalIndicator(BaseModel):
    """Layer 3 temporal: Trend analysis for a single signal."""
    signal: str
    momentum: float = 0.0                      # Rate of change
    persistence: float = 0.0                   # Sustained presence ratio
    is_spike: bool = False                     # Sudden jump > 2σ
    spike_severity: float = 0.0                # σ-score of spike
    trend_label: str = "stable"                # accelerating, stable, decelerating


class DomainIndex(BaseModel):
    """Layer 3 domain: Fuzzy-aggregated domain score."""
    capability: float = 0.0                    # Military power signals
    intent: float = 0.0                        # Hostile signaling
    instability: float = 0.0                   # Internal unrest
    cost: float = 0.0                          # Economic/diplomatic costs
    logistics: float = 0.0                     # Supply-chain and sustainment signals
    intent_profile: Dict[str, float] = Field(default_factory=dict) # Theory of mind profile
    contributors: Dict[str, List[str]] = Field(default_factory=dict)


class EscalationResult(BaseModel):
    """Layer 3 output: Multi-dimensional escalation assessment."""
    escalation_score: float = 0.0              # Composite [0.0, 1.0]
    threat_level: str = "LOW"                  # LOW, MODERATE, ELEVATED, HIGH, CRITICAL
    domain_indices: DomainIndex = Field(default_factory=DomainIndex)
    trend_bonus: float = 0.0
    temporal_spike_bonus: float = 0.0
    mobilization_triggered: bool = False
    mobilization_bonus: float = 0.0
    logistics_triggered: bool = False
    logistics_bonus: float = 0.0
    capability_floor_applied: bool = False
    conflict_floor_applied: bool = False
    escalation_trace: List[Dict[str, Any]] = Field(default_factory=list)


class FuzzySignalBelief(BaseModel):
    """Next-gen Layer 3 belief: fuzzy, source-aware signal support."""
    signal_code: str
    fuzzy_set: str = "unknown"
    membership: float = 0.0
    reliability: float = 0.0
    recency: float = 1.0
    evidence_support: float = 0.0
    source_agreement: float = 0.0
    temporal_stability: float = 0.0
    uncertainty: float = 0.0
    source_count: int = 0
    source_types: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    eligible_for_sre: bool = True
    exclusion_reason: Optional[str] = None
    fuzzy_memberships: Dict[str, float] = Field(default_factory=dict)


class ObservedSignal(BaseModel):
    """Next-gen projected signal used by empirical SRE."""
    signal_code: str
    domain: str = "unknown"
    membership: float = 0.0
    reliability: float = 0.0
    recency: float = 1.0
    evidence_support: float = 0.0
    confidence: float = 0.0
    fuzzy_memberships: Dict[str, float] = Field(default_factory=dict)
    source_refs: List[str] = Field(default_factory=list)
    excluded_from_sre: bool = False
    exclusion_reason: Optional[str] = None


class SREDomainFusion(BaseModel):
    """Next-gen SRE domain fusion output."""
    capability: float = 0.0
    intent: float = 0.0
    stability: float = 0.0
    cost: float = 0.0
    contributors: Dict[str, List[str]] = Field(default_factory=dict)


class SREInputTrace(BaseModel):
    """Next-gen SRE escalation inputs and trigger state."""
    base_score: float = 0.0
    trend_bonus: float = 0.0
    temporal_spike_bonus: float = 0.0
    mobilization_trigger: bool = False
    mobilization_bonus: float = 0.0
    logistics_trigger: bool = False
    logistics_bonus: float = 0.0
    capability_floor_applied: bool = False
    conflict_floor_applied: bool = False
    confidence_decay: float = 1.0
    active_conflicts: List[str] = Field(default_factory=list)


class NextGenSREOutput(BaseModel):
    """First-class core contract for the next-gen fuzzy SRE pipeline."""
    fuzzy_memberships: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    signal_beliefs: List[FuzzySignalBelief] = Field(default_factory=list)
    projected_signals: List[ObservedSignal] = Field(default_factory=list)
    sre_domains: SREDomainFusion = Field(default_factory=SREDomainFusion)
    sre_input: SREInputTrace = Field(default_factory=SREInputTrace)
    sre_escalation_score: float = 0.0
    risk_level: str = "LOW"
    qualitative_bands: Dict[str, str] = Field(default_factory=dict)
    escalation_trace: List[Dict[str, Any]] = Field(default_factory=list)
    legal_firewall_rejections: List[Dict[str, str]] = Field(default_factory=list)


class BayesianTrace(BaseModel):
    """Mathematical trace of posterior probability updates."""
    observation_id: str
    prior_probability: float
    posterior_probability: float
    evidence_weight: float
    hypothesis: str

class Contradiction(BaseModel):
    """Explicit logging of conflicting signals."""
    signal_a_id: str
    signal_b_id: str
    conflict_description: str
    resolution_rationale: str
    winning_signal_id: Optional[str] = None

class IntelligenceGap(BaseModel):
    """Identified blindspots in the current collection."""
    missing_information: str
    domain: str
    priority: str = "Medium"
    expected_information_gain: float = 0.0

class RFIQuery(BaseModel):
    """An autonomously generated Request for Information (RFI)."""
    query: str
    target_domains: List[str] = Field(default_factory=list)
    priority: str = "MEDIUM"                 # HIGH, MEDIUM, LOW
    estimated_time_mins: float = 0.0
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0
    justification: str = ""

class ResearchLogEntry(BaseModel):
    """Tracks the lifecycle of an RFI."""
    rfi: RFIQuery
    status: str = "GENERATED"                # GENERATED, EXECUTED, EVIDENCE_FOUND, ACCEPTED, REJECTED
    evidence_found: int = 0
    execution_time_ms: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
class ReadinessReport(BaseModel):
    """Granular readiness score deciding if reasoning can begin."""
    score: float = 0.0
    is_ready: bool = False
    evidence_coverage: float = 0.0
    graph_connectivity: float = 0.0
    temporal_coverage: float = 0.0
    source_diversity: float = 0.0
    contradiction_score: float = 0.0
    expert_agreement: float = 0.0
    missing_entities: List[str] = Field(default_factory=list)
    missing_relationships: List[str] = Field(default_factory=list)
    rfi_queries: List[RFIQuery] = Field(default_factory=list)
    estimated_cost: float = 0.0
    estimated_time: float = 0.0
    iteration: int = 1

class StateContext(BaseModel):
    """Layer 3 output: The World Model. Must not contain LLM reasoning."""
    country: str
    current_signals: List[Signal] = Field(default_factory=list)
    beliefs: List[Belief] = Field(default_factory=list)
    temporal_indicators: List[TemporalIndicator] = Field(default_factory=list)
    escalation: Optional[EscalationResult] = None
    nextgen_sre: Optional[NextGenSREOutput] = None
    historical_context: Dict[str, Any] = Field(default_factory=dict)
    active_conflicts: List[str] = Field(default_factory=list)
    observation_count: int = 0
    confidence_decay: float = 1.0              # 1.0 = fully confident, <1.0 = blindspots
    data_blindspots: List[str] = Field(default_factory=list)
    bayesian_traces: List[BayesianTrace] = Field(default_factory=list)
    contradictions: List[Contradiction] = Field(default_factory=list)
    intelligence_gaps: List[IntelligenceGap] = Field(default_factory=list)
    source_profiles: Dict[str, SourceProfile] = Field(default_factory=dict)


class MinisterCritiqueOutput(BaseModel):
    """Schema for a minister critiquing another minister's hypothesis."""
    concurrence: str # "Concur", "Concur with Comment", "Non-Concur"
    justification: str
    
class MinisterRecalibrationOutput(BaseModel):
    """Schema for a minister updating their confidence based on critiques."""
    recalibrated_confidence: float
    recalibration_rationale: str
    
# =====================================================================
# Layer 4 — Analysis (Council)
# =====================================================================

class DebateCritique(BaseModel):
    """A critique issued by one minister against another minister's hypothesis."""
    critiquing_minister: str
    target_minister: str
    concurrence: str  # "Concur", "Concur with Comment", "Non-Concur"
    justification: str

class Hypothesis(BaseModel):
    """Layer 4 unit: A testable explanation generated by a Minister."""
    source: str = "AI"
    minister: str
    hypothesis_type: str
    predicted_signals: List[str]
    matched_signals: List[str]
    missing_signals: List[str]
    confidence: float
    decision_mode: str = "heuristic"
    heuristic_confidence: Optional[float] = None
    llm_confidence: Optional[float] = None
    agreement_score: Optional[float] = None
    disagreement_notes: List[str] = Field(default_factory=list)
    critiques: List[DebateCritique] = Field(default_factory=list)
    recalibrated_confidence: Optional[float] = None
    recalibration_rationale: Optional[str] = None


class MergedHypothesis(Hypothesis):
    """A combined hypothesis maintaining provenance from Dual-Engine."""
    source: str = "Merged"
    heuristic_source: Optional[Hypothesis] = None
    ai_source: Optional[Hypothesis] = None



class MinisterHypothesisOutput(BaseModel):
    """Schema-constrained minister output from heuristic or LLM refinement."""

    source: str = "AI"
    minister: str = ""
    hypothesis_type: str = ""
    predicted_signals: List[str] = Field(default_factory=list)
    matched_signals: List[str] = Field(default_factory=list)
    missing_signals: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""
    critical_signal_refs: List[str] = Field(default_factory=list)

    @field_validator("predicted_signals", "matched_signals", "missing_signals", "critical_signal_refs", mode="before")
    @classmethod
    def normalize_string_list(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in list(value or [])]


class DualModeMinisterDecision(BaseModel):
    """Heuristic-first, LLM-refined minister decision trace."""

    minister: str
    hypothesis_type: str
    heuristic: MinisterHypothesisOutput
    llm: Optional[MinisterHypothesisOutput] = None
    final: MinisterHypothesisOutput
    agreement_score: float = Field(default=1.0, ge=0.0, le=1.0)
    resolution_action: str = "heuristic_only"
    disagreement_notes: List[str] = Field(default_factory=list)


class AssessmentDecision(BaseModel):
    """Layer 4 output: The final decision of the council."""
    threat_level: str                          # LOW, MODERATE, ELEVATED, HIGH, CRITICAL
    justification: str
    confidence: float


# =====================================================================
# Layer 5 — Trajectory & Black Swan
# =====================================================================

class ScenarioNode(BaseModel):
    """A node in the scenario tree."""
    scenario_type: str # Best Case, Most Likely, Worst Case, Black Swan
    description: str
    probability: float
    trigger_events: List[str] = Field(default_factory=list)

class ScenarioTree(BaseModel):
    """Layer 5 output: Branching forward projections."""
    base_trajectory: str
    nodes: List[ScenarioNode] = Field(default_factory=list)

class TrajectoryForecast(BaseModel):
    """Layer 5 output: Forward-looking escalation probabilities."""
    prob_14d: float = 0.0                      # P(HIGH in 14 days)
    prob_30d: float = 0.0                      # P(HIGH in 30 days)
    prob_60d: float = 0.0                      # P(HIGH in 60 days)
    velocity: float = 0.0                      # Rate of escalation change
    trajectory_label: str = "STABLE"           # ESCALATING, STABLE, DE_ESCALATING


class BlackSwanResult(BaseModel):
    """Layer 5 output: Discontinuity event detection."""
    triggered: bool = False
    reasons: List[str] = Field(default_factory=list)
    channels_fired: List[str] = Field(default_factory=list)
    escalation_boost: float = 0.0
    trajectory_floor: float = 0.0
    confidence_cap: float = 1.0
    mandatory_review: bool = False


# =====================================================================
# Layer 6 — Learning & Memory
# =====================================================================

class LearningReport(BaseModel):
    """Layer 6 output: Self-improvement analysis."""
    accuracy_trend: float = 0.0                # Recent accuracy rate
    calibration_error: float = 0.0             # |confidence - accuracy|
    blind_spots: List[str] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)
    confidence_adjustment: float = 1.0         # Multiplier for future runs


# =====================================================================
# Layer 7 — Global Contagion
# =====================================================================

class ContagionResult(BaseModel):
    """Layer 7 output: Cross-theater spillover effects."""
    source_country: str
    spillovers: Dict[str, float] = Field(default_factory=dict)
    total_contagion: float = 0.0


# =====================================================================
# Layer 8 — War Gaming (Scenario Engine)
# =====================================================================

class WargameAction(BaseModel):
    """Layer 8 input: The hypothetical action taken by the Prime Minister."""
    description: str
    target_country: Optional[str] = None


class WargameResult(BaseModel):
    """Layer 8 output: The full simulation results of a hypothetical action."""
    action: WargameAction
    synthetic_signals: List[Signal] = Field(default_factory=list)
    escalation_delta: float = 0.0              # Change in target's escalation
    global_spillovers: Dict[str, float] = Field(default_factory=dict)
    consequence_briefing: str = ""             # LLM-generated analysis of counter-moves
    simulation_outcomes: Dict[str, Any] = Field(default_factory=dict)

# =====================================================================
# QA Feedback Schema Enhancements
# =====================================================================

class ThreatDimensions(BaseModel):
    military: float = 0.0
    diplomatic: float = 0.0
    economic: float = 0.0
    cyber: float = 0.0
    information: float = 0.0

class IntelligenceAssessment(BaseModel):
    """Structured output from the Threat Synthesizer."""
    threat_dimensions: ThreatDimensions = Field(default_factory=ThreatDimensions)
    overall_threat_level: str = "LOW"
    overall_confidence: float = 0.0
    positive_evidence: List[Signal] = Field(default_factory=list)
    negative_evidence: List[Signal] = Field(default_factory=list)
    unknown_factors: List[str] = Field(default_factory=list)
    collection_gaps: List[str] = Field(default_factory=list) # Ranked priorities
    timeline_events: List[str] = Field(default_factory=list)
    alternative_hypotheses: List[str] = Field(default_factory=list)
    forecast_24h: float = 0.0
    forecast_7d: float = 0.0
    forecast_30d: float = 0.0
    recommendations: List[str] = Field(default_factory=list)
    assessment_stability: str = "Stable"


class DualModeAssessment(BaseModel):
    """Phase 8: Neuro-symbolic synthesis capturing both paths and their agreement."""
    heuristic_result: IntelligenceAssessment
    llm_result: Optional[IntelligenceAssessment] = None
    final: IntelligenceAssessment
    agreement_score: float = Field(default=1.0, ge=0.0, le=1.0)
    disagreements: List[str] = Field(default_factory=list)
    resolution_action: str = "heuristic_only"
    confidence_adjustment: float = 0.0

# =====================================================================
# Layer 9 — Decision Support
# =====================================================================

class DecisionOption(BaseModel):
    """Actionable recommendations with pros, cons, and risks."""
    option_id: str
    title: str
    description: str
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    cost: str
    risk_level: str
    probability_of_success: float
    expected_outcome: str
