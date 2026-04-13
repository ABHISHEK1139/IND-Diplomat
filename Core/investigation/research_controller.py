"""
Investigation controller bridge (state -> gap -> plan -> collection -> rebuild).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Callable, Optional

from sqlalchemy import or_

from Core.investigation.gap_detector import detect_gap_report
from Core.investigation.investigation_planner import generate_queries


COUNTRY_ALIASES = {
    "usa": "USA",
    "united states": "USA",
    "u.s.": "USA",
    "us": "USA",
    "china": "CHN",
    "prc": "CHN",
    "taiwan": "TWN",
    "japan": "JPN",
    "india": "IND",
}

COUNTRY_DB_LABELS = {
    "USA": {"USA", "United States"},
    "CHN": {"China", "CHN"},
    "TWN": {"Taiwan", "TWN"},
    "JPN": {"Japan", "JPN"},
    "IND": {"India", "IND"},
}


@dataclass
class InvestigationOutcome:
    question: str
    status: str
    gaps: List[str] = field(default_factory=list)
    planner_queries: List[str] = field(default_factory=list)
    collected_documents: int = 0
    documents_by_query: Dict[str, int] = field(default_factory=dict)
    knowledge_commit: Dict[str, Any] = field(default_factory=dict)
    state_update: Dict[str, Any] = field(default_factory=dict)
    investigation_outcome: str = ""
    confidence_update: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    executed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "status": self.status,
            "gaps": self.gaps,
            "planner_queries": self.planner_queries,
            "collected_documents": self.collected_documents,
            "documents_by_query": self.documents_by_query,
            "knowledge_commit": self.knowledge_commit,
            "state_update": self.state_update,
            "investigation_outcome": self.investigation_outcome,
            "confidence_update": self.confidence_update,
            "notes": self.notes,
            "executed_at": self.executed_at,
        }


class InvestigationController:
    """
    Orchestrates gap-driven data collection and state refresh.
    """

    def __init__(
        self,
        search_runner: Optional[Callable[..., Dict[str, List[Dict[str, Any]]]]] = None,
        knowledge_ingestor: Optional[Callable[[List[Dict[str, Any]]], Any]] = None,
        state_rebuilder: Optional[Callable[..., Dict[str, Any]]] = None,
    ):
        self._search_runner = search_runner or _default_search_runner
        self._knowledge_ingestor = knowledge_ingestor or _default_knowledge_ingestor
        self._state_rebuilder = state_rebuilder or _default_state_rebuilder

    def run_investigation(
        self,
        question: str,
        country_state: Any,
        relationship_state: Any,
    ) -> InvestigationOutcome:
        """
        Run bridge workflow:
        1) detect gaps
        2) generate queries
        3) run MoltBot collection
        4) rebuild Layer-3 state
        """
        report = detect_gap_report(question, country_state, relationship_state)
        if not report.gaps:
            return InvestigationOutcome(
                question=question,
                status="no_investigation_required",
                notes=["All required evidence categories are already satisfied."],
            )

        queries = generate_queries(question, report.gaps)
        countries = _extract_countries(question)
        search_payload = self._search_runner(
            queries,
            required_evidence=report.required_categories,
            countries=countries,
            missing_gaps=report.gaps,
        )

        docs_by_query = {query: len(docs or []) for query, docs in (search_payload or {}).items()}
        collected_total = sum(docs_by_query.values())
        all_documents: List[Dict[str, Any]] = []
        for docs in (search_payload or {}).values():
            all_documents.extend(docs or [])

        commit_result = self._knowledge_ingestor(all_documents)
        if hasattr(commit_result, "to_dict"):
            commit_payload = commit_result.to_dict()
        elif isinstance(commit_result, dict):
            commit_payload = commit_result
        else:
            commit_payload = {"value": commit_result}

        state_update = self._state_rebuilder(
            question=question,
            countries=countries,
            missing_gaps=report.gaps,
        )

        from Layer3_Reasoning.investigation_outcome import classify_outcome
        from engine.Layer3_StateModel.validation.confidence_calculator import update_confidence

        old_confidence = _extract_average_confidence(country_state)
        new_information = _as_float(
            commit_payload.get("new_information", commit_payload.get("effective_information", 0.0))
        )
        existing_information = _as_float(commit_payload.get("existing_information", 0.0))
        updated_confidence = update_confidence(
            old_confidence=old_confidence,
            new_information=new_information,
            existing_information=existing_information,
        )
        contradiction_count = _extract_contradiction_count(state_update)
        outcome_label = classify_outcome(new_information, contradiction_count)
        confidence_update = {
            "before": round(old_confidence, 6),
            "after": round(updated_confidence, 6),
            "delta": round(updated_confidence - old_confidence, 6),
            "new_information": round(new_information, 6),
            "existing_information": round(existing_information, 6),
        }

        if isinstance(state_update, dict):
            state_update["investigation_outcome"] = outcome_label
            state_update["confidence_update"] = confidence_update
            state_update["information_gain"] = round(new_information, 6)
            country_states = state_update.get("country_states")
            if isinstance(country_states, dict):
                for payload in country_states.values():
                    if not isinstance(payload, dict):
                        continue
                    analysis = payload.setdefault("analysis_confidence", {})
                    prior = _as_float(analysis.get("overall_score", old_confidence))
                    analysis["overall_score_before"] = round(prior, 6)
                    analysis["overall_score_after"] = round(updated_confidence, 6)
                    analysis["overall_score"] = round(updated_confidence, 6)

        return InvestigationOutcome(
            question=question,
            status="investigation_complete",
            gaps=report.gaps,
            planner_queries=queries,
            collected_documents=collected_total,
            documents_by_query=docs_by_query,
            knowledge_commit=commit_payload,
            state_update=state_update,
            investigation_outcome=outcome_label,
            confidence_update=confidence_update,
            notes=[report.reasons.get(gap, "") for gap in report.gaps if report.reasons.get(gap)],
        )


def run_investigation(
    question: str,
    country_state: Any,
    relationship_state: Any,
) -> InvestigationOutcome:
    """
    Compatibility entrypoint used by package exports.
    """
    controller = InvestigationController()
    return controller.run_investigation(
        question=question,
        country_state=country_state,
        relationship_state=relationship_state,
    )


def run_feedback_investigation(
    question: str,
    needed_information: List[str],
    countries: List[str]
) -> InvestigationOutcome:
    """
    Driven by Layer-4 feedback.
    Bypasses gap detection and searches for specific needed information.
    """
    controller = InvestigationController()
    
    # We construct a synthetic 'gap' list from needed info
    # and force the search runner to use it.
    
    queries = [f"{question} {info}" for info in needed_information]
    
    search_payload = controller._search_runner(
        queries,
        required_evidence=[str(i) for i in needed_information], # Treat as categories
        countries=countries or _extract_countries(question),
        missing_gaps=needed_information,
    )

    # Ingest
    docs_by_query = {query: len(docs or []) for query, docs in (search_payload or {}).items()}
    all_documents: List[Dict[str, Any]] = []
    for docs in (search_payload or {}).values():
        all_documents.extend(docs or [])

    commit_result = controller._knowledge_ingestor(all_documents)
    
    # Rebuild
    state_update = controller._state_rebuilder(
        question=question,
        countries=countries,
        missing_gaps=needed_information,
    )
    
    return InvestigationOutcome(
        question=question,
        status="feedback_investigation_complete",
        gaps=needed_information,
        planner_queries=queries,
        collected_documents=len(all_documents),
        documents_by_query=docs_by_query,
        state_update=state_update,
        investigation_outcome="feedback_loop_closed"
    )


def _default_search_runner(
    queries: List[str],
    *,
    required_evidence: List[str],
    countries: List[str],
    missing_gaps: List[str],
) -> Dict[str, List[Dict[str, Any]]]:
    from moltbot.search import run_search_tasks

    return run_search_tasks(
        queries,
        required_evidence=required_evidence,
        countries=countries,
        missing_gaps=missing_gaps,
    )


def _default_knowledge_ingestor(documents: List[Dict[str, Any]]):
    from engine.Layer2_Knowledge.assimilation.investigation_ingestor import ingest_documents

    return ingest_documents(documents)


def _default_state_rebuilder(
    *,
    question: str,
    countries: List[str],
    missing_gaps: List[str],
) -> Dict[str, Any]:
    """
    Default Layer-3 refresh path after collection.
    """
    from Core.database.models import Event
    from Core.database.session import get_session
    from engine.Layer3_StateModel.analysis_readiness import evaluate_analysis_readiness
    from engine.Layer3_StateModel.country_state_builder import build_state, state_builder
    from engine.Layer3_StateModel.relationship_state_builder import build_relationship_state
    from contracts.observation import ActionType, ObservationRecord, SourceType

    selected = countries or _extract_countries(question)
    if not selected:
        selected = ["USA", "CHN"]

    today = datetime.utcnow().strftime("%Y-%m-%d")
    start = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")

    # Ensure rebuild reflects newly committed knowledge.
    if hasattr(state_builder, "_legal_signal_cache"):
        state_builder._legal_signal_cache.clear()
    if hasattr(state_builder, "_legal_shift_cache"):
        state_builder._legal_shift_cache.clear()
    if hasattr(state_builder, "_validation_obs_cache"):
        state_builder._validation_obs_cache.clear()

    country_states: Dict[str, Any] = {}
    for code in selected:
        try:
            vector = build_state(code, today)
            payload = vector.to_dict()
            legal_pack = vector.signal_breakdown.get("legal_signals", {}) or {}
            payload["legal_signal_count"] = int(legal_pack.get("signal_count", 0))
            payload["legal_justification_presence"] = (
                "active" if payload["legal_signal_count"] > 0 else "inactive"
            )
            country_states[code] = payload
        except Exception:
            country_states[code] = {"error": f"failed to rebuild {code}"}

    relationship_state = None
    if len(selected) >= 2:
        left = selected[0]
        right = selected[1]
        observations: List[ObservationRecord] = []
        db = get_session()
        try:
            left_labels = list(COUNTRY_DB_LABELS.get(left, {left}))
            right_labels = list(COUNTRY_DB_LABELS.get(right, {right}))
            rows = (
                db.query(Event)
                .filter(
                    Event.event_date >= start,
                    or_(
                        Event.actor1.in_(left_labels + right_labels),
                        Event.actor2.in_(left_labels + right_labels),
                    ),
                )
                .all()
            )
            for row in rows:
                a1 = _normalize_country_code(str(row.actor1 or ""))
                a2 = _normalize_country_code(str(row.actor2 or ""))
                if not a1 or not a2:
                    continue
                obs = ObservationRecord(
                    obs_id=f"rebuild_evt_{row.id}",
                    source="gdelt",
                    source_type=SourceType.EVENT_MONITOR,
                    event_date=str(row.event_date or today)[:10],
                    report_date=str(row.event_date or today)[:10],
                    actors=[a1, a2],
                    action_type=_event_type_to_action(str(row.event_type or ""), float(row.intensity or 0.0)),
                    intensity=max(0.0, min(1.0, float(row.intensity or 0.0))),
                    direction=f"{a1} -> {a2}",
                    confidence=0.70,
                    raw_reference=str(row.source or ""),
                )
                observations.append(obs)
        finally:
            db.close()

        if observations:
            try:
                relationship_state = build_relationship_state(
                    observations=observations,
                    country_a=left,
                    country_b=right,
                    start_date=start,
                    end_date=today,
                    reference_date=today,
                ).to_dict()
            except Exception:
                relationship_state = {"error": "failed to rebuild relationship_state"}

    readiness = evaluate_analysis_readiness(
        country_state=list(country_states.values()),
        relationship_state=relationship_state or {},
    ).to_dict()

    return {
        "countries": selected,
        "missing_gaps": missing_gaps,
        "country_states": country_states,
        "relationship_state": relationship_state,
        "analysis_readiness": readiness,
        "rebuilt_at": datetime.utcnow().isoformat() + "Z",
    }


def _extract_countries(question: str) -> List[str]:
    lower = str(question or "").lower()
    found: List[str] = []
    for alias, code in COUNTRY_ALIASES.items():
        if alias in lower and code not in found:
            found.append(code)
    return found


def _extract_average_confidence(country_state: Any) -> float:
    states: List[Dict[str, Any]] = []
    if isinstance(country_state, dict):
        if isinstance(country_state.get("country_states"), dict):
            states.extend(
                [row for row in country_state["country_states"].values() if isinstance(row, dict)]
            )
        else:
            states.append(country_state)
    elif isinstance(country_state, list):
        states.extend([row for row in country_state if isinstance(row, dict)])

    scores: List[float] = []
    for state in states:
        score = _as_float(
            ((state.get("analysis_confidence") or {}).get("overall_score"))
            if isinstance(state.get("analysis_confidence"), dict)
            else None
        )
        if score <= 0.0:
            score = _as_float(
                ((state.get("signal_breakdown") or {}).get("validation_confidence", {}).get("overall_score"))
                if isinstance(state.get("signal_breakdown"), dict)
                else None
            )
        if score <= 0.0:
            score = _as_float((state.get("evidence") or {}).get("layer3_validation_confidence"))
        if score > 0.0:
            scores.append(score)

    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _extract_contradiction_count(state_update: Any) -> int:
    if not isinstance(state_update, dict):
        return 0
    relationship = state_update.get("relationship_state")
    if isinstance(relationship, dict):
        score = relationship.get("confidence")
        if isinstance(score, dict):
            contradictions = score.get("contradiction_count")
            try:
                return max(0, int(contradictions))
            except Exception:
                return 0
    return 0


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _normalize_country_code(label: str) -> str:
    text = str(label or "").strip().lower()
    if text in ("usa", "united states", "u.s.", "us"):
        return "USA"
    if text in ("china", "chn", "prc"):
        return "CHN"
    if text in ("taiwan", "twn"):
        return "TWN"
    if text in ("india", "ind"):
        return "IND"
    if len(text) == 3 and text.isalpha():
        return text.upper()
    return ""


def _event_type_to_action(event_type: str, intensity: float):
    from contracts.observation import ActionType

    by_root = {
        "01": ActionType.STATEMENT,
        "02": ActionType.CONSULTATION,
        "03": ActionType.COOPERATION,
        "04": ActionType.DIPLOMACY,
        "05": ActionType.COOPERATION,
        "06": ActionType.COOPERATION,
        "07": ActionType.AID,
        "08": ActionType.COOPERATION,
        "09": ActionType.OBSERVATION,
        "10": ActionType.PRESSURE,
        "11": ActionType.PRESSURE,
        "12": ActionType.PRESSURE,
        "13": ActionType.THREATEN_MILITARY,
        "14": ActionType.PROTEST,
        "15": ActionType.MOBILIZE,
        "16": ActionType.TRADE_RESTRICTION,
        "17": ActionType.PRESSURE,
        "18": ActionType.VIOLENCE,
        "19": ActionType.WAR,
        "20": ActionType.WAR,
    }
    code = str(event_type or "").strip()
    if code in by_root:
        return by_root[code]
    if intensity >= 0.8:
        return ActionType.THREATEN_MILITARY
    if intensity >= 0.5:
        return ActionType.PRESSURE
    return ActionType.STATEMENT


investigation_controller = InvestigationController()

__all__ = [
    "InvestigationOutcome",
    "InvestigationController",
    "investigation_controller",
    "run_investigation",
]
