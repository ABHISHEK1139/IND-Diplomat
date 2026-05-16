"""
Self-directed learning loop for IND-Diplomat.

This module turns runtime friction into explicit learning goals:

    observe -> reflect -> choose goals -> propose experiments -> remember

It is intentionally bounded. The agent may create goals, rank them, and
record experiment outcomes, but it does not rewrite code, ingest new sources,
or change thresholds without the existing calibration/approval gates.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger("Layer6_Learning.self_directed_learning")

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_MEMORY_PATH = os.path.join(_DATA_DIR, "self_directed_memory.json")
_file_lock = threading.Lock()

MAX_ACTIVE_GOALS = 25
DEFAULT_MAX_SELECTED_GOALS = 5


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _read_field(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple) or isinstance(value, set):
        return list(value)
    return [value]


def _stable_id(*parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _dedupe_strings(values: Iterable[Any], limit: int = 12) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= limit:
            break
    return result


@dataclass
class LearningTrigger:
    """A runtime condition that asks the system to learn something."""

    kind: str
    severity: float
    reason: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["severity"] = round(_clamp(self.severity), 4)
        return payload


@dataclass
class LearningGoal:
    """A bounded, inspectable goal created by self-reflection."""

    id: str
    kind: str
    country: str
    objective: str
    priority: float
    reason: str
    target_metric: str
    desired_direction: str
    suggested_actions: List[str] = field(default_factory=list)
    safeguards: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    status: str = "open"
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["priority"] = round(_clamp(self.priority), 4)
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearningGoal":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in dict(data or {}).items() if k in known})


@dataclass
class LearningExperiment:
    """A proposed or recorded experiment linked to a learning goal."""

    goal_id: str
    name: str
    method: str
    metric: str
    expected_effect: str
    success_criteria: str
    rollback_rule: str
    status: str = "proposed"
    created_at: str = field(default_factory=_utc_now)
    result: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearningExperiment":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in dict(data or {}).items() if k in known})


@dataclass
class SelfDirectedCycle:
    """Result of one self-directed reflection pass."""

    cycle_id: str
    created_at: str
    country: str
    autonomy_level: str
    human_approval_required: bool
    triggers: List[LearningTrigger] = field(default_factory=list)
    selected_goals: List[LearningGoal] = field(default_factory=list)
    proposed_experiments: List[LearningExperiment] = field(default_factory=list)
    memory_summary: Dict[str, Any] = field(default_factory=dict)
    safety_policy: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "created_at": self.created_at,
            "country": self.country,
            "autonomy_level": self.autonomy_level,
            "human_approval_required": self.human_approval_required,
            "triggers": [t.to_dict() for t in self.triggers],
            "selected_goals": [g.to_dict() for g in self.selected_goals],
            "proposed_experiments": [e.to_dict() for e in self.proposed_experiments],
            "memory_summary": dict(self.memory_summary),
            "safety_policy": list(self.safety_policy),
        }


class SelfDirectedMemory:
    """Small JSON memory for goals and experiment outcomes."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or _MEMORY_PATH

    def load(self) -> Dict[str, Any]:
        with _file_lock:
            if not os.path.exists(self.path):
                return {"goals": [], "experiments": [], "updated_at": None}
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if not isinstance(data, dict):
                    return {"goals": [], "experiments": [], "updated_at": None}
                data.setdefault("goals", [])
                data.setdefault("experiments", [])
                return data
            except (OSError, json.JSONDecodeError):
                logger.warning("[SELF-LEARNING] Corrupt memory; starting with empty memory")
                return {"goals": [], "experiments": [], "updated_at": None}

    def save(self, data: Dict[str, Any]) -> None:
        with _file_lock:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            data = dict(data or {})
            data["updated_at"] = _utc_now()
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)

    def merge_goals(self, goals: List[LearningGoal]) -> Dict[str, Any]:
        data = self.load()
        existing: Dict[str, Dict[str, Any]] = {
            str(item.get("id")): dict(item)
            for item in data.get("goals", [])
            if isinstance(item, dict) and item.get("id")
        }

        for goal in goals:
            current = existing.get(goal.id)
            if current:
                current["priority"] = max(_safe_float(current.get("priority")), goal.priority)
                current["reason"] = goal.reason
                current["evidence"] = goal.evidence
                current["suggested_actions"] = goal.suggested_actions
                current["safeguards"] = goal.safeguards
                current["updated_at"] = _utc_now()
                current["status"] = current.get("status") or "open"
            else:
                existing[goal.id] = goal.to_dict()

        ordered = sorted(
            existing.values(),
            key=lambda item: (_safe_float(item.get("priority")), str(item.get("updated_at") or "")),
            reverse=True,
        )
        data["goals"] = ordered[:MAX_ACTIVE_GOALS]
        self.save(data)
        return data

    def append_experiments(self, experiments: List[LearningExperiment]) -> Dict[str, Any]:
        data = self.load()
        existing_ids = {
            _stable_id(item.get("goal_id"), item.get("name"), item.get("method"))
            for item in data.get("experiments", [])
            if isinstance(item, dict)
        }
        rows = list(data.get("experiments", []) or [])
        for exp in experiments:
            exp_id = _stable_id(exp.goal_id, exp.name, exp.method)
            if exp_id not in existing_ids:
                row = exp.to_dict()
                row["id"] = exp_id
                rows.append(row)
                existing_ids.add(exp_id)
        data["experiments"] = rows[-100:]
        self.save(data)
        return data

    def summary(self) -> Dict[str, Any]:
        data = self.load()
        goals = [g for g in data.get("goals", []) if isinstance(g, dict)]
        experiments = [e for e in data.get("experiments", []) if isinstance(e, dict)]
        open_goals = [g for g in goals if str(g.get("status", "open")).lower() == "open"]
        accepted = [e for e in experiments if str(e.get("status", "")).lower() == "accepted"]
        return {
            "open_goals": len(open_goals),
            "stored_goals": len(goals),
            "stored_experiments": len(experiments),
            "accepted_experiments": len(accepted),
            "updated_at": data.get("updated_at"),
        }


class SelfDirectedLearningAgent:
    """Bounded metacognitive agent for self-directed improvement."""

    safety_policy = [
        "No autonomous code edits or dependency installation.",
        "No threshold changes outside calibration caps and approval gates.",
        "No new data-source activation without provenance and operator approval.",
        "Learning goals must be tied to measurable evidence quality, calibration, or reasoning quality.",
    ]

    def __init__(
        self,
        memory_path: Optional[str] = None,
        max_selected_goals: int = DEFAULT_MAX_SELECTED_GOALS,
    ):
        self.memory = SelfDirectedMemory(memory_path)
        self.max_selected_goals = max(1, int(max_selected_goals))

    def reflect(self, session: Any, persist: bool = True) -> SelfDirectedCycle:
        """Inspect a completed session and create bounded learning goals."""
        context = self._extract_context(session)
        triggers = self._build_triggers(context)
        goals = self._build_goals(context, triggers)
        selected = sorted(goals, key=lambda goal: goal.priority, reverse=True)[: self.max_selected_goals]
        experiments = [self._experiment_for_goal(goal) for goal in selected]

        if persist and selected:
            self.memory.merge_goals(selected)
            self.memory.append_experiments(experiments)

        cycle = SelfDirectedCycle(
            cycle_id=_stable_id(context["country"], context["session_id"], context["created_at"]),
            created_at=context["created_at"],
            country=context["country"],
            autonomy_level="bounded_assistive",
            human_approval_required=True,
            triggers=triggers,
            selected_goals=selected,
            proposed_experiments=experiments,
            memory_summary=self.memory.summary(),
            safety_policy=list(self.safety_policy),
        )
        return cycle

    def record_experiment_result(
        self,
        goal_id: str,
        name: str,
        metric: str,
        before: float,
        after: float,
        accepted: bool,
        notes: str = "",
    ) -> Dict[str, Any]:
        """Record whether an experiment improved the target metric."""
        exp = LearningExperiment(
            goal_id=str(goal_id),
            name=str(name),
            method="operator_supplied_result",
            metric=str(metric),
            expected_effect="Recorded after execution",
            success_criteria="Accepted by operator or validation metric improved",
            rollback_rule="Reject and keep previous production behavior",
            status="accepted" if accepted else "rejected",
            result={
                "before": round(float(before), 6),
                "after": round(float(after), 6),
                "delta": round(float(after) - float(before), 6),
                "notes": str(notes or ""),
                "recorded_at": _utc_now(),
            },
        )
        data = self.memory.append_experiments([exp])
        return {
            "experiment": exp.to_dict(),
            "memory_summary": self.memory.summary(),
            "stored_experiments": len(data.get("experiments", []) or []),
        }

    def _extract_context(self, session: Any) -> Dict[str, Any]:
        state_context = _read_field(session, "state_context", None)
        actors = _read_field(state_context, "actors", None)
        meta = _read_field(state_context, "meta", None)
        gate_verdict = _read_field(session, "gate_verdict", None)
        gap_report = _read_field(session, "gap_report", None)
        full_context = _read_field(session, "full_context", None)

        country = (
            _read_field(actors, "subject_country", None)
            or _read_field(session, "learning_country", None)
            or _read_field(session, "country", None)
            or "UNKNOWN"
        )

        hypotheses = _as_list(_read_field(session, "hypotheses", []))
        coverages = [
            _clamp(_safe_float(_read_field(h, "coverage", 0.0)))
            for h in hypotheses
            if _read_field(h, "coverage", None) is not None
        ]
        avg_coverage = round(sum(coverages) / len(coverages), 6) if coverages else 0.0

        missing_signals = _dedupe_strings(
            list(_read_field(session, "missing_signals", []) or [])
            + list(_read_field(session, "investigation_needs", []) or [])
        )
        contradictions = _dedupe_strings(
            list(_read_field(full_context, "contradictions", []) or [])
            + list(_read_field(gap_report, "contradictions", []) or [])
            + list(_read_field(session, "identified_conflicts", []) or [])
        )
        gaps = _dedupe_strings(
            list(_read_field(full_context, "gaps", []) or [])
            + list(_read_field(gap_report, "gaps", []) or [])
        )

        reports = (
            _as_list(_read_field(session, "ministers_reports", []))
            + _as_list(_read_field(session, "round1_reports", []))
            + _as_list(_read_field(session, "round2_reports", []))
        )
        monitor_issues: List[str] = []
        degraded_count = 0
        for report in reports:
            monitor_issues.extend(_as_list(_read_field(report, "reasoning_monitor_issues", [])))
            monitor_issues.extend(_as_list(_read_field(report, "self_critique_issues", [])))
            if bool(_read_field(report, "classification_degraded", False)) or bool(
                _read_field(report, "reasoning_degraded", False)
            ):
                degraded_count += 1

        calibration = {}
        try:
            from engine.Layer6_Learning.calibration_engine import calibration_score

            calibration = calibration_score(str(country) if country else None)
        except Exception:
            calibration = {}

        signal_confidence = _read_field(full_context, "signal_confidence", {}) or {}
        uncertain_signals = []
        if isinstance(signal_confidence, dict):
            uncertain_signals = [
                str(name)
                for name, value in sorted(signal_confidence.items(), key=lambda item: _safe_float(item[1]))
                if _safe_float(value, 1.0) < 0.35
            ][:8]

        return {
            "created_at": _utc_now(),
            "session_id": str(_read_field(session, "session_id", "") or ""),
            "country": str(country or "UNKNOWN").upper(),
            "status": str(_read_field(session, "status", "") or ""),
            "risk_level": str(_read_field(session, "king_decision", "") or ""),
            "final_confidence": _clamp(_safe_float(_read_field(session, "final_confidence", 0.0))),
            "epistemic_confidence": _clamp(_safe_float(_read_field(session, "epistemic_confidence", 0.0))),
            "sensor_confidence": _clamp(_safe_float(_read_field(session, "sensor_confidence", 0.0))),
            "source_count": _safe_int(_read_field(meta, "source_count", 0), 0),
            "avg_hypothesis_coverage": avg_coverage,
            "hypothesis_count": len(hypotheses),
            "missing_signals": missing_signals,
            "contradictions": contradictions,
            "gaps": gaps,
            "monitor_issues": _dedupe_strings(monitor_issues),
            "degraded_report_count": degraded_count,
            "gate_passed": bool(_read_field(gate_verdict, "passed", True)),
            "gate_reasons": _dedupe_strings(_read_field(gate_verdict, "reasons", []) or []),
            "calibration": calibration,
            "uncertain_signals": uncertain_signals,
        }

    def _build_triggers(self, context: Dict[str, Any]) -> List[LearningTrigger]:
        triggers: List[LearningTrigger] = []
        coverage = _safe_float(context.get("avg_hypothesis_coverage"), 0.0)
        missing = list(context.get("missing_signals", []) or [])
        contradictions = list(context.get("contradictions", []) or [])
        gaps = list(context.get("gaps", []) or [])
        calibration = dict(context.get("calibration", {}) or {})
        monitor_issues = list(context.get("monitor_issues", []) or [])

        if coverage < 0.45 or len(missing) >= 3:
            severity = max(1.0 - coverage, min(1.0, len(missing) / 8.0))
            triggers.append(
                LearningTrigger(
                    kind="evidence_gap",
                    severity=severity,
                    reason="Hypothesis coverage or missing signal volume indicates weak evidence.",
                    evidence={"coverage": coverage, "missing_signals": missing[:8]},
                )
            )

        if contradictions:
            triggers.append(
                LearningTrigger(
                    kind="contradiction",
                    severity=min(1.0, 0.35 + len(contradictions) * 0.12),
                    reason="Contradictory claims or state signals need resolution.",
                    evidence={"contradictions": contradictions[:8]},
                )
            )

        if gaps:
            triggers.append(
                LearningTrigger(
                    kind="knowledge_gap",
                    severity=min(1.0, 0.25 + len(gaps) * 0.08),
                    reason="The analysis exposed missing contextual knowledge.",
                    evidence={"gaps": gaps[:8]},
                )
            )

        if not bool(context.get("gate_passed", True)):
            triggers.append(
                LearningTrigger(
                    kind="gate_failure",
                    severity=0.85,
                    reason="Assessment gate blocked or withheld the answer.",
                    evidence={"gate_reasons": list(context.get("gate_reasons", []) or [])[:8]},
                )
            )

        tier = str(calibration.get("tier", "") or "").upper()
        if tier == "MISCALIBRATED":
            triggers.append(
                LearningTrigger(
                    kind="calibration_error",
                    severity=0.9,
                    reason="Resolved forecasts indicate miscalibration.",
                    evidence={
                        "avg_brier": calibration.get("avg_brier"),
                        "n_resolved": calibration.get("n_resolved"),
                    },
                )
            )
        elif tier == "INSUFFICIENT":
            triggers.append(
                LearningTrigger(
                    kind="forecast_learning_debt",
                    severity=0.35,
                    reason="Forecast archive needs more resolved cases before weight learning.",
                    evidence={
                        "n_resolved": calibration.get("n_resolved", 0),
                        "min_required": calibration.get("min_required", 20),
                    },
                )
            )

        if monitor_issues or _safe_int(context.get("degraded_report_count"), 0) > 0:
            triggers.append(
                LearningTrigger(
                    kind="reasoning_quality",
                    severity=min(1.0, 0.35 + len(monitor_issues) * 0.08),
                    reason="Reasoning monitor or LLM degradation detected quality risks.",
                    evidence={
                        "issues": monitor_issues[:8],
                        "degraded_report_count": context.get("degraded_report_count", 0),
                    },
                )
            )

        if context.get("uncertain_signals"):
            triggers.append(
                LearningTrigger(
                    kind="uncertainty_hotspot",
                    severity=min(1.0, 0.25 + len(context["uncertain_signals"]) * 0.06),
                    reason="Several signals have low confidence and high learning value.",
                    evidence={"signals": context["uncertain_signals"][:8]},
                )
            )

        return sorted(triggers, key=lambda item: item.severity, reverse=True)

    def _build_goals(self, context: Dict[str, Any], triggers: List[LearningTrigger]) -> List[LearningGoal]:
        goals: List[LearningGoal] = []
        country = str(context.get("country") or "UNKNOWN")

        for trigger in triggers:
            if trigger.kind == "evidence_gap":
                missing = _dedupe_strings(trigger.evidence.get("missing_signals", []), limit=6)
                goals.append(
                    LearningGoal(
                        id=_stable_id(country, "evidence_gap", ",".join(missing)),
                        kind="evidence_acquisition",
                        country=country,
                        objective="Increase coverage for the highest-impact missing signals.",
                        priority=max(0.55, trigger.severity),
                        reason=trigger.reason,
                        target_metric="avg_hypothesis_coverage",
                        desired_direction="increase",
                        suggested_actions=[
                            "Create VOI-ranked PIRs for the missing signals.",
                            "Require independent provenance before promoting observations to beliefs.",
                            "Re-run the same query after collection and compare coverage delta.",
                        ],
                        safeguards=[
                            "Do not promote single-source claims above the belief threshold.",
                            "Keep collection within configured OSINT/provider boundaries.",
                        ],
                        evidence=trigger.evidence,
                    )
                )
            elif trigger.kind == "contradiction":
                goals.append(
                    LearningGoal(
                        id=_stable_id(country, "contradiction", ",".join(trigger.evidence.get("contradictions", []))),
                        kind="contradiction_resolution",
                        country=country,
                        objective="Resolve contradictory evidence before raising confidence.",
                        priority=max(0.60, trigger.severity),
                        reason=trigger.reason,
                        target_metric="contradiction_count",
                        desired_direction="decrease",
                        suggested_actions=[
                            "Run a counterfactual pass for each conflicting claim.",
                            "Ask the contrarian minister to explain which source would falsify the consensus.",
                            "Prefer newer, primary, and independently corroborated evidence.",
                        ],
                        safeguards=[
                            "Do not discard minority evidence without provenance review.",
                            "Keep the final confidence penalty until contradictions shrink.",
                        ],
                        evidence=trigger.evidence,
                    )
                )
            elif trigger.kind == "gate_failure":
                goals.append(
                    LearningGoal(
                        id=_stable_id(country, "gate_failure", ",".join(trigger.evidence.get("gate_reasons", []))),
                        kind="gate_recovery",
                        country=country,
                        objective="Learn why the assessment gate withheld output and close the blocker.",
                        priority=0.9,
                        reason=trigger.reason,
                        target_metric="gate_pass_rate",
                        desired_direction="increase",
                        suggested_actions=[
                            "Map each gate reason to a required evidence or confidence action.",
                            "Run a narrow investigation cycle against only gate-blocking PIRs.",
                            "Keep WITHHELD status until the deterministic gate passes.",
                        ],
                        safeguards=[
                            "Never bypass the assessment gate.",
                            "Escalate to human review for high-impact predictions.",
                        ],
                        evidence=trigger.evidence,
                    )
                )
            elif trigger.kind == "calibration_error":
                goals.append(
                    LearningGoal(
                        id=_stable_id(country, "calibration", trigger.evidence.get("avg_brier")),
                        kind="model_calibration",
                        country=country,
                        objective="Reduce forecast error using replay-backed calibration.",
                        priority=0.92,
                        reason=trigger.reason,
                        target_metric="avg_brier",
                        desired_direction="decrease",
                        suggested_actions=[
                            "Run crisis replay on resolved forecasts for this theater.",
                            "Apply only capped auto-adjuster deltas that improve Brier score.",
                            "Compare structural-only and full-council calibration before rollout.",
                        ],
                        safeguards=[
                            "Respect the 20 percent drift cap on adjustable constants.",
                            "Keep a rollback snapshot of previous calibration values.",
                        ],
                        evidence=trigger.evidence,
                    )
                )
            elif trigger.kind == "forecast_learning_debt":
                goals.append(
                    LearningGoal(
                        id=_stable_id(country, "forecast_learning_debt"),
                        kind="forecast_resolution",
                        country=country,
                        objective="Accumulate enough resolved forecasts to learn safely.",
                        priority=0.42,
                        reason=trigger.reason,
                        target_metric="n_resolved_forecasts",
                        desired_direction="increase",
                        suggested_actions=[
                            "Continue archiving forecasts with explicit horizon and outcome definition.",
                            "Resolve stale forecasts as ground truth becomes available.",
                        ],
                        safeguards=[
                            "Do not auto-adjust from underpowered samples.",
                        ],
                        evidence=trigger.evidence,
                    )
                )
            elif trigger.kind == "reasoning_quality":
                goals.append(
                    LearningGoal(
                        id=_stable_id(country, "reasoning_quality", ",".join(trigger.evidence.get("issues", []))),
                        kind="reasoning_quality",
                        country=country,
                        objective="Improve reasoning discipline for degraded or low-quality stages.",
                        priority=max(0.50, trigger.severity),
                        reason=trigger.reason,
                        target_metric="reasoning_quality_score",
                        desired_direction="increase",
                        suggested_actions=[
                            "Lower effort for easy stages and raise effort only for uncertain, high-stakes stages.",
                            "Add self-critique only when signal density or contradiction pressure warrants it.",
                            "Compare concise and expanded minister outputs on the same evidence pack.",
                        ],
                        safeguards=[
                            "Do not increase token budgets globally without validation.",
                            "Keep deterministic fallback paths active.",
                        ],
                        evidence=trigger.evidence,
                    )
                )
            elif trigger.kind == "uncertainty_hotspot":
                goals.append(
                    LearningGoal(
                        id=_stable_id(country, "uncertainty", ",".join(trigger.evidence.get("signals", []))),
                        kind="active_learning",
                        country=country,
                        objective="Target uncertainty hotspots that can change the conclusion.",
                        priority=max(0.45, trigger.severity),
                        reason=trigger.reason,
                        target_metric="low_confidence_signal_count",
                        desired_direction="decrease",
                        suggested_actions=[
                            "Pass low-confidence signals through the CuriosityController VOI ranking.",
                            "Collect only signals whose expected information value crosses threshold.",
                        ],
                        safeguards=[
                            "Stop collection when uncertainty reduction stalls across repeated cycles.",
                        ],
                        evidence=trigger.evidence,
                    )
                )
            elif trigger.kind == "knowledge_gap":
                goals.append(
                    LearningGoal(
                        id=_stable_id(country, "knowledge_gap", ",".join(trigger.evidence.get("gaps", []))),
                        kind="knowledge_assimilation",
                        country=country,
                        objective="Assimilate missing contextual knowledge into retrievable memory.",
                        priority=max(0.40, trigger.severity),
                        reason=trigger.reason,
                        target_metric="knowledge_gap_count",
                        desired_direction="decrease",
                        suggested_actions=[
                            "Convert each gap into a source-backed knowledge request.",
                            "Index only documents with provenance and extraction timestamps.",
                            "Re-score retrieval support before using new context in analysis.",
                        ],
                        safeguards=[
                            "Separate empirical evidence from legal or normative context.",
                            "Do not let unverified background context override observed signals.",
                        ],
                        evidence=trigger.evidence,
                    )
                )

        unique: Dict[str, LearningGoal] = {}
        for goal in goals:
            if goal.id not in unique or goal.priority > unique[goal.id].priority:
                unique[goal.id] = goal
        return list(unique.values())

    def _experiment_for_goal(self, goal: LearningGoal) -> LearningExperiment:
        if goal.kind == "model_calibration":
            return LearningExperiment(
                goal_id=goal.id,
                name="replay_calibration_ablation",
                method="Run replay twice: current settings versus capped proposed adjustment.",
                metric=goal.target_metric,
                expected_effect="Lower average Brier score without exceeding drift caps.",
                success_criteria="Brier improves by at least 0.02 on resolved forecasts.",
                rollback_rule="Reject adjustment if Brier worsens or any drift cap is hit.",
            )
        if goal.kind == "evidence_acquisition":
            return LearningExperiment(
                goal_id=goal.id,
                name="voi_collection_trial",
                method="Collect the top VOI PIRs, rebuild state, and compare hypothesis coverage.",
                metric=goal.target_metric,
                expected_effect="Coverage increases and missing signals decrease.",
                success_criteria="Coverage rises by at least 0.10 or one critical PIR is resolved.",
                rollback_rule="Discard new beliefs that lack independent provenance.",
            )
        if goal.kind == "contradiction_resolution":
            return LearningExperiment(
                goal_id=goal.id,
                name="counterfactual_contradiction_test",
                method="Run counterfactual and contrarian passes against the conflicting claims.",
                metric=goal.target_metric,
                expected_effect="Contradiction count decreases or confidence is correctly penalized.",
                success_criteria="At least one contradiction is resolved with provenance.",
                rollback_rule="Keep contradiction penalty if no side is independently supported.",
            )
        if goal.kind == "reasoning_quality":
            return LearningExperiment(
                goal_id=goal.id,
                name="reasoning_budget_comparison",
                method="Compare concise versus high-effort reasoning on the same evidence pack.",
                metric=goal.target_metric,
                expected_effect="Higher signal density with no loss of grounding.",
                success_criteria="Reasoning quality score improves and hallucination flags do not rise.",
                rollback_rule="Return to previous effort policy if quality does not improve.",
            )
        return LearningExperiment(
            goal_id=goal.id,
            name=f"{goal.kind}_validation",
            method="Run a narrow before/after validation pass for the selected learning goal.",
            metric=goal.target_metric,
            expected_effect=f"{goal.target_metric} should {goal.desired_direction}.",
            success_criteria="Measured metric moves in the desired direction without safety violations.",
            rollback_rule="Keep previous production behavior if validation fails.",
        )


def assess_self_directed_learning(
    session: Any,
    persist: bool = True,
    memory_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience wrapper used by the pipeline output builder."""
    agent = SelfDirectedLearningAgent(memory_path=memory_path)
    return agent.reflect(session, persist=persist).to_dict()


__all__ = [
    "LearningTrigger",
    "LearningGoal",
    "LearningExperiment",
    "SelfDirectedCycle",
    "SelfDirectedMemory",
    "SelfDirectedLearningAgent",
    "assess_self_directed_learning",
]
