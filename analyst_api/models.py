"""
Pydantic v2 models for the Analyst API.
All structured contracts for requests, jobs, results, evidence.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────

class TimeHorizon(str, Enum):
    SHORT  = "7d"
    MEDIUM = "30d"
    LONG   = "90d"


class EvidenceStrictness(str, Enum):
    CAUTIOUS   = "cautious"      # highlight anything below 0.6
    BALANCED   = "balanced"      # default engine behaviour
    AGGRESSIVE = "aggressive"    # accept weaker evidence


class SourceMode(str, Enum):
    DATASET = "dataset"          # GDELT only
    OSINT   = "osint"            # MoltBot only
    HYBRID  = "hybrid"           # both (default)


class GateThreshold(str, Enum):
    DEFAULT      = "default"     # engine defaults
    STRICT       = "strict"      # require confidence >= 0.65
    EXPERIMENTAL = "experimental" # lower bar, more assessments released


class CollectionDepth(str, Enum):
    FAST     = "fast"            # max_investigation_loops=1
    STANDARD = "standard"        # max_investigation_loops=2
    DEEP     = "deep"            # max_investigation_loops=3


class JobPhase(str, Enum):
    QUEUED         = "QUEUED"
    SCOPE_CHECK    = "SCOPE_CHECK"
    SENSORS        = "SENSORS"
    COUNCIL        = "COUNCIL"
    GATE           = "GATE"
    REPORT         = "REPORT"
    COMPLETED      = "COMPLETED"
    FAILED         = "FAILED"


# ── Request ────────────────────────────────────────────────────────────

class AssessmentRequest(BaseModel):
    """Parameters for a new intelligence assessment."""
    query: str = Field(..., min_length=10, max_length=4000,
                       description="Intelligence question / mission request")
    country_code: str = Field("IRN", max_length=5,
                              description="ISO-3166 alpha-3 country code")
    time_horizon: TimeHorizon = TimeHorizon.MEDIUM
    evidence_strictness: EvidenceStrictness = EvidenceStrictness.BALANCED
    source_mode: SourceMode = SourceMode.HYBRID
    gate_threshold: GateThreshold = GateThreshold.DEFAULT
    collection_depth: CollectionDepth = CollectionDepth.STANDARD
    use_red_team: bool = True
    use_mcts: bool = False


# ── Job Status ─────────────────────────────────────────────────────────

class PhaseUpdate(BaseModel):
    phase: JobPhase
    detail: str = ""
    started_at: str = ""
    elapsed_sec: float = 0.0


class JobStatus(BaseModel):
    job_id: str
    status: JobPhase
    phase: JobPhase
    phase_detail: str = ""
    progress_pct: int = 0
    phases_completed: List[PhaseUpdate] = []
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    elapsed_sec: float = 0.0
    error: str = ""


# ── Evidence ───────────────────────────────────────────────────────────

class EvidenceAtom(BaseModel):
    signal_name: str
    source_type: str       # GDELT, OSINT/MoltBot, RAG, Legal, EconomicReasoner, derived
    source_detail: str = ""
    confidence: float = 0.0
    timestamp: str = ""
    dimension: str = ""    # CAPABILITY, INTENT, STABILITY, COST, UNKNOWN
    raw_snippet: str = ""


# ── SRE ────────────────────────────────────────────────────────────────

class SREDecomposition(BaseModel):
    capability: float = 0.0
    intent: float = 0.0
    stability: float = 0.0
    cost: float = 0.0
    trend_bonus: float = 0.0
    escalation_score: float = 0.0
    risk_level: str = "UNKNOWN"
    formula: str = "0.35×cap + 0.30×int + 0.20×stab + 0.15×cost + trend"


# ── Gate ───────────────────────────────────────────────────────────────

class GateVerdictModel(BaseModel):
    approved: bool = False
    decision: str = "UNKNOWN"
    reasons: List[str] = []
    intelligence_gaps: List[str] = []
    collection_tasks: List[Dict[str, Any]] = []
    proposed_decision: str = ""
    confidence: float = 0.0


# ── Verification Chain ─────────────────────────────────────────────────

class VerificationStep(BaseModel):
    step: int
    title: str
    description: str
    data: Dict[str, Any] = {}


class VerificationChain(BaseModel):
    steps: List[VerificationStep] = []
    total_steps: int = 0


# ── Council Summary ───────────────────────────────────────────────────

class MinisterReport(BaseModel):
    name: str
    dimension: str
    confidence: float = 0.0
    coverage: float = 0.0
    predicted_signals: List[str] = []


class CouncilSummary(BaseModel):
    ministers: List[MinisterReport] = []
    sensor_confidence: float = 0.0
    document_confidence: float = 0.0
    epistemic_confidence: float = 0.0
    analytic_confidence: float = 0.0
    verification_score: float = 0.0
    grounding_passed: bool = False
    evidence_atom_count: int = 0
    investigation_rounds: int = 0
    hypotheses: List[Dict[str, Any]] = []


# ── Temporal / Trend ──────────────────────────────────────────────────

class TrendPoint(BaseModel):
    timestamp: str
    country: str = ""
    escalation_score: float = 0.0
    risk_level: str = ""
    domains: Dict[str, float] = {}   # cap/int/stab/cost


class TemporalTrend(BaseModel):
    snapshot_count: int = 0
    escalation_patterns: int = 0
    spikes: int = 0
    pattern_signals: List[str] = []
    indicators: Dict[str, Any] = {}


# ── Full Assessment Result ────────────────────────────────────────────

class AssessmentResult(BaseModel):
    """Complete structured output for a finished assessment."""
    job_id: str = ""
    outcome: str = ""               # ASSESSMENT / INSUFFICIENT_EVIDENCE / OUT_OF_SCOPE
    answer: str = ""
    risk_level: str = ""
    confidence: float = 0.0
    analytic_confidence: float = 0.0
    epistemic_confidence: float = 0.0
    early_warning_index: float = 0.0

    # Structured decompositions
    sre: Optional[SREDecomposition] = None
    gate_verdict: Optional[GateVerdictModel] = None
    council: Optional[CouncilSummary] = None
    temporal: Optional[TemporalTrend] = None

    # Evidence & verification
    evidence_chain: List[EvidenceAtom] = []
    verification_chain: Optional[VerificationChain] = None

    # Trend data (from monitor log)
    trend_data: List[TrendPoint] = []

    # Formatted report (text)
    formatted_report: str = ""

    # Raw warnings
    operational_warnings: List[str] = []
    whitebox: Optional[Dict[str, Any]] = None

    # Request params echo
    request: Optional[AssessmentRequest] = None


# ── Job List Item ─────────────────────────────────────────────────────

class JobListItem(BaseModel):
    job_id: str
    status: str
    query_preview: str = ""
    country_code: str = ""
    risk_level: str = ""
    confidence: float = 0.0
    created_at: str = ""
    elapsed_sec: float = 0.0
