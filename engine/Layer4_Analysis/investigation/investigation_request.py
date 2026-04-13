"""
Structured investigation task request emitted by Layer-4.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from engine.Layer4_Analysis.evidence.signal_ontology import canonicalize_signal_token
from engine.layer4_reasoning.signal_queries import SIGNAL_COLLECTION_MAP


class InvestigationReason(str, Enum):
    DISAGREEMENT = "disagreement"
    LOW_CONFIDENCE = "low_confidence"
    MISSING_EVIDENCE = "missing_evidence"
    VERIFICATION_FAILURE = "verification_failure"


@dataclass
class InvestigationRequest:
    signal_token: str
    collection_target: str
    priority: str
    query: str

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "signal_token": self.signal_token,
            "collection_target": self.collection_target,
            "priority": self.priority,
            "query": self.query,
        }
        # Compatibility passthrough for legacy fields used in tests/debug tools.
        for key in (
            "question",
            "reason",
            "confidence",
            "missing_evidence",
            "search_queries",
            "conflicting_ministers",
            "context_snapshot",
        ):
            if hasattr(self, key):
                payload[key] = getattr(self, key)
        return payload


def _infer_reason(session: Any) -> InvestigationReason:
    # Keep explicit references for current CouncilSession schema:
    # identified_conflicts, ministers_reports, final_confidence.
    conflicts = list(getattr(session, "identified_conflicts", []) or [])
    _reports = list(getattr(session, "ministers_reports", []) or [])
    confidence = float(getattr(session, "final_confidence", 0.0) or 0.0)
    missing = list(getattr(session, "missing_signals", []) or [])

    if conflicts:
        return InvestigationReason.DISAGREEMENT
    if missing:
        return InvestigationReason.MISSING_EVIDENCE
    if confidence < 0.45:
        return InvestigationReason.LOW_CONFIDENCE
    return InvestigationReason.MISSING_EVIDENCE


def _normalize_missing_signals(session: Any) -> List[str]:
    raw = list(getattr(session, "missing_signals", []) or [])
    out: List[str] = []
    seen = set()
    for item in raw:
        text = str(item or "").strip()
        if not text:
            continue
        token = canonicalize_signal_token(text) or text
        norm = token.lower()
        if norm in seen:
            continue
        seen.add(norm)
        out.append(token)
    return out


def _build_queries(question: str, missing_signals: List[str], max_queries: int) -> List[str]:
    queries: List[str] = []
    for signal in missing_signals:
        mapped = SIGNAL_COLLECTION_MAP.get(signal)
        if mapped:
            queries.append(mapped)
            continue
        queries.append(signal.replace("_", " "))

    out: List[str] = []
    seen = set()
    for q in queries:
        text = " ".join(str(q).split()).strip()
        if not text:
            continue
        token = text.lower()
        if token in seen:
            continue
        seen.add(token)
        out.append(text)
        if len(out) >= max(1, int(max_queries)):
            break
    return out


def build_investigation_request(
    session: Any,
    reason: Optional[InvestigationReason] = None,
    max_queries: int = 4,
) -> InvestigationRequest:
    """
    Build one high-priority collection request from current missing signals.

    Compatibility note:
    The returned object is the new InvestigationRequest task object but
    includes legacy attributes (`question`, `reason`, `confidence`,
    `missing_evidence`, `search_queries`) used by existing tests and tooling.
    """
    question = str(getattr(session, "question", "") or "")
    confidence = float(getattr(session, "final_confidence", 0.0) or 0.0)
    missing_signals = _normalize_missing_signals(session)
    resolved_reason = reason or _infer_reason(session)
    queries = _build_queries(question, missing_signals, max_queries=max_queries)

    signal_token = missing_signals[0] if missing_signals else "SIG_MIL_ESCALATION"
    query = queries[0] if queries else SIGNAL_COLLECTION_MAP.get(signal_token, signal_token.replace("_", " "))

    request = InvestigationRequest(
        signal_token=signal_token,
        collection_target="OSINT_FEEDS",
        priority="HIGH",
        query=query,
    )

    # Legacy/diagnostic fields for existing code paths.
    request.question = question
    request.reason = resolved_reason
    request.confidence = confidence
    request.missing_evidence = list(missing_signals)
    request.search_queries = list(queries)
    request.conflicting_ministers = [str(c) for c in list(getattr(session, "identified_conflicts", []) or [])[:6]]
    request.context_snapshot = {
        "session_id": getattr(session, "session_id", ""),
        "loop_count": int(getattr(session, "loop_count", 0) or 0),
        "turn_count": int(getattr(session, "turn_count", 0) or 0),
    }
    return request


__all__ = ["InvestigationReason", "InvestigationRequest", "build_investigation_request"]

