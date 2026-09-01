"""Contracts for the next-generation head-of-state advisory layer.

These models are intentionally small and framework-neutral.  LangGraph,
Prefect, MLflow, OpenTelemetry, Haystack, STIX, or NetworkX integrations
should adapt to these contracts instead of leaking their own schemas into
the intelligence core.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_trace_id(seed: str) -> str:
    digest = sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"dip2-{digest}"


class PipelinePhase(str, Enum):
    GOAL_INTAKE = "GOAL_INTAKE"
    COLLECTION = "COLLECTION"
    FUZZY_PROJECTION = "FUZZY_PROJECTION"
    SRE = "SRE"
    COUNCIL = "COUNCIL"
    INVESTIGATION = "INVESTIGATION"
    GATE = "GATE"
    REPORT = "REPORT"
    LEARNING = "LEARNING"

class AdvisoryMode(str, Enum):
    """The advisory stance requested by the decision maker."""

    SITUATION_BRIEF = "situation_brief"
    OPTIONS_ANALYSIS = "options_analysis"
    CRISIS_CELL = "crisis_cell"
    RED_TEAM = "red_team"
    WAR_GAME = "war_game"


class DecisionPosture(str, Enum):
    """How forceful the system may be in recommending action."""

    INFORM = "inform"
    WARN = "warn"
    RECOMMEND = "recommend"
    WITHHOLD = "withhold"


class SafetyBoundary(BaseModel):
    """Non-negotiable advisory constraints."""

    name: str
    rule: str
    severity: str = "hard"


class AssessmentGoal(BaseModel):
    """Durable goal object for a strategic advisory run."""

    objective: str
    country: str = "UNKNOWN"
    theater: Optional[str] = None
    mode: AdvisoryMode = AdvisoryMode.SITUATION_BRIEF
    success_criteria: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    safety_boundaries: List[SafetyBoundary] = Field(default_factory=list)
    risk_tolerance: str = "low"
    trace_id: str = ""
    created_at: str = Field(default_factory=_now)

    @field_validator("objective")
    @classmethod
    def objective_required(cls, value: str) -> str:
        clean = str(value or "").strip()
        if not clean:
            raise ValueError("objective is required")
        return clean

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        clean = str(value or "UNKNOWN").strip().upper()
        return clean or "UNKNOWN"

    def model_post_init(self, __context: Any) -> None:
        if not self.trace_id:
            seed = f"{self.objective}|{self.country}|{self.theater or ''}|{self.created_at}"
            self.trace_id = _stable_trace_id(seed)
        if not self.success_criteria:
            self.success_criteria = [
                "evidence-backed situation picture",
                "explicit uncertainty and blindspots",
                "ranked options with second-order effects",
                "clear human review points",
            ]
        if not self.safety_boundaries:
            self.safety_boundaries = default_safety_boundaries()


class BlackboardEvent(BaseModel):
    """Append-only event emitted by the advisory graph."""

    trace_id: str
    phase: str
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    source: str = "dip2.nextgen"
    created_at: str = Field(default_factory=_now)


class LearningUnit(BaseModel):
    """A small learnable gap found during an assessment."""

    trace_id: str
    topic: str
    trigger: str
    success_test: str
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)
    status: str = "planned"


class ExperimentRecord(BaseModel):
    """Controlled experiment before changing default behavior."""

    trace_id: str
    hypothesis: str
    method: str
    metric: str
    success_threshold: str
    rollback_rule: str
    status: str = "planned"
    result: Dict[str, Any] = Field(default_factory=dict)


class PromotionStatus(BaseModel):
    """Governance record for adopting a new heuristic, prompt, or threshold."""

    candidate: str
    approved: bool = False
    evidence: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)


class HeadOfStateBriefing(BaseModel):
    """Decision-maker facing output envelope."""

    goal: AssessmentGoal
    decision_posture: DecisionPosture = DecisionPosture.INFORM
    executive_summary: str = ""
    evidence_findings: List[str] = Field(default_factory=list)
    options: List[Dict[str, Any]] = Field(default_factory=list)
    risk_matrix: Dict[str, Any] = Field(default_factory=dict)
    uncertainty: List[str] = Field(default_factory=list)
    red_team_challenges: List[str] = Field(default_factory=list)
    required_human_decisions: List[str] = Field(default_factory=list)
    next_collection_tasks: List[str] = Field(default_factory=list)
    fuzzy_trace: Dict[str, Any] = Field(default_factory=dict)
    blackboard_events: List[BlackboardEvent] = Field(default_factory=list)
    learning_units: List[LearningUnit] = Field(default_factory=list)
    experiment_records: List[ExperimentRecord] = Field(default_factory=list)
    promotion_status: List[PromotionStatus] = Field(default_factory=list)


def default_safety_boundaries() -> List[SafetyBoundary]:
    """Default constraints for a head-of-state helper."""

    return [
        SafetyBoundary(
            name="human_authority",
            rule="The system advises; accountable humans decide.",
        ),
        SafetyBoundary(
            name="evidence_first",
            rule="Separate evidence, inference, forecast, and recommendation.",
        ),
        SafetyBoundary(
            name="no_covert_action",
            rule="Do not plan deception, covert influence, or unlawful operations.",
        ),
        SafetyBoundary(
            name="legal_humanitarian_review",
            rule="Flag options requiring legal, treaty, humanitarian, or democratic oversight.",
        ),
        SafetyBoundary(
            name="uncertainty_disclosure",
            rule="Never hide low confidence, source gaps, or contradictory evidence.",
        ),
    ]


def create_assessment_goal(
    objective: str,
    *,
    country: str = "UNKNOWN",
    theater: Optional[str] = None,
    mode: AdvisoryMode = AdvisoryMode.SITUATION_BRIEF,
    constraints: Optional[List[str]] = None,
) -> AssessmentGoal:
    """Factory used by CLI/API layers to create a durable advisory goal."""

    return AssessmentGoal(
        objective=objective,
        country=country,
        theater=theater,
        mode=mode,
        constraints=list(constraints or []),
    )
