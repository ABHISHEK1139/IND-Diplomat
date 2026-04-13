"""
Case domain models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class CaseStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class CaseRecord:
    """
    Long-lived investigation record.
    """

    case_id: str
    question: str
    actors: List[str] = field(default_factory=list)
    start_time: str = ""
    current_hypothesis: str = ""
    missing_evidence: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    confidence: float = 0.0
    status: CaseStatus = CaseStatus.OPEN
    analysis_history: List[Dict[str, Any]] = field(default_factory=list)
    rejected_hypotheses: List[str] = field(default_factory=list)
    search_history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        now = datetime.utcnow().isoformat() + "Z"
        if not self.start_time:
            self.start_time = now
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    @classmethod
    def new(
        cls,
        question: str,
        actors: Optional[List[str]] = None,
        hypothesis: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "CaseRecord":
        return cls(
            case_id=f"case_{uuid.uuid4().hex[:12]}",
            question=question,
            actors=list(actors or []),
            current_hypothesis=hypothesis,
            metadata=dict(metadata or {}),
        )

