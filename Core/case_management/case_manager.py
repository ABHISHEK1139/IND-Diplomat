"""
High-level case manager facade.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from .case import CaseRecord, CaseStatus
from .case_store import CaseStore


class CaseManager:
    """
    Orchestrates case lifecycle with persistence.
    """

    def __init__(self, store: Optional[CaseStore] = None):
        self._store = store or CaseStore()

    def create_case(
        self,
        question: str,
        actors: Optional[List[str]] = None,
        hypothesis: str = "",
        metadata: Optional[Dict[str, object]] = None,
    ) -> CaseRecord:
        record = CaseRecord.new(
            question=question,
            actors=actors or [],
            hypothesis=hypothesis,
            metadata=metadata or {},
        )
        record.status = CaseStatus.INVESTIGATING
        self._store.upsert(record)
        return record

    def get_case(self, case_id: str) -> Optional[CaseRecord]:
        return self._store.get(case_id)

    def update_case_status(
        self,
        case_id: str,
        status: CaseStatus,
        confidence: Optional[float] = None,
        missing_evidence: Optional[List[str]] = None,
    ) -> Optional[CaseRecord]:
        case = self._store.get(case_id)
        if not case:
            return None
        case.status = status
        if confidence is not None:
            case.confidence = max(0.0, min(1.0, float(confidence)))
        if missing_evidence is not None:
            case.missing_evidence = list(missing_evidence)
        case.updated_at = datetime.utcnow().isoformat() + "Z"
        self._store.upsert(case)
        return case

    def attach_evidence_ids(self, case_id: str, evidence_ids: List[str]) -> Optional[CaseRecord]:
        case = self._store.get(case_id)
        if not case:
            return None
        merged = list(dict.fromkeys(case.evidence_ids + list(evidence_ids)))
        case.evidence_ids = merged
        self._store.upsert(case)
        return case

    def add_search_step(
        self,
        case_id: str,
        query: str,
        indexes: Optional[List[str]] = None,
        gaps: Optional[List[str]] = None,
    ) -> Optional[CaseRecord]:
        case = self._store.get(case_id)
        if not case:
            return None
        case.search_history.append(
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "query": query,
                "indexes": list(indexes or []),
                "gaps": list(gaps or []),
            }
        )
        self._store.upsert(case)
        return case

    def add_analysis_round(
        self,
        case_id: str,
        round_number: int,
        sufficiency_before: float,
        sufficiency_after: float,
        notes: Optional[str] = None,
    ) -> Optional[CaseRecord]:
        case = self._store.get(case_id)
        if not case:
            return None
        case.analysis_history.append(
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "round": int(round_number),
                "sufficiency_before": float(sufficiency_before),
                "sufficiency_after": float(sufficiency_after),
                "notes": notes or "",
            }
        )
        self._store.upsert(case)
        return case

    def reject_hypothesis(self, case_id: str, hypothesis: str) -> Optional[CaseRecord]:
        case = self._store.get(case_id)
        if not case:
            return None
        if hypothesis and hypothesis not in case.rejected_hypotheses:
            case.rejected_hypotheses.append(hypothesis)
        self._store.upsert(case)
        return case

    def list_recent(self, limit: int = 20) -> List[CaseRecord]:
        return self._store.list_recent(limit=limit)


case_manager = CaseManager()

__all__ = ["CaseManager", "case_manager"]

