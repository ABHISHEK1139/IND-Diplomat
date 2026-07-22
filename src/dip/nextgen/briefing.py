"""Head-of-country briefing builder."""

from __future__ import annotations

from typing import Any, Dict, List

from .contracts import (
    DecisionPosture,
    ExperimentRecord,
    HeadOfStateBriefing,
    LearningUnit,
    PromotionStatus,
)
from .knowledge_graph import StrategicKnowledgeGraph
from .perception import build_fuzzy_trace, compute_strategic_pressure


def _risk_options(risk_level: str, pressure: Dict[str, Any]) -> List[Dict[str, Any]]:
    risk = str(risk_level or "LOW").upper()
    urgency = float(pressure.get("urgency", 0.0) or 0.0)
    diplomatic_window = float(pressure.get("diplomatic_window", 0.0) or 0.0)

    options = [
        {
            "name": "Intensify collection",
            "posture": "low-risk",
            "purpose": "Close intelligence gaps before committing policy.",
            "second_order_effects": ["Slower response", "Higher confidence", "Less escalation risk"],
        },
        {
            "name": "Open or reinforce diplomatic channel",
            "posture": "de-escalatory",
            "purpose": "Preserve bargaining space and reduce miscalculation.",
            "second_order_effects": ["May be read as restraint", "Creates off-ramp", "Requires message discipline"],
        },
        {
            "name": "Prepare visible defensive readiness",
            "posture": "deterrent",
            "purpose": "Signal resolve while avoiding offensive commitment.",
            "second_order_effects": ["Can deter", "Can also trigger reciprocal mobilization", "Needs allied coordination"],
        },
    ]

    if risk in {"HIGH", "CRITICAL"} or urgency > 0.70:
        options.insert(
            0,
            {
                "name": "Convene crisis cell",
                "posture": "urgent",
                "purpose": "Synchronize intelligence, diplomacy, military readiness, legal review, and communications.",
                "second_order_effects": ["Faster decisions", "Higher coordination load", "Risk of public signal leakage"],
            },
        )

    if diplomatic_window < 0.20 and risk in {"HIGH", "CRITICAL"}:
        options.append(
            {
                "name": "Backchannel deconfliction",
                "posture": "quiet de-escalation",
                "purpose": "Reduce accidental escalation when public diplomacy is constrained.",
                "second_order_effects": ["Hard to verify", "Requires trusted intermediary", "Can preserve face-saving exit"],
            }
        )

    return options[:4]


def _posture_for_result(result: Dict[str, Any], pressure: Dict[str, Any]) -> DecisionPosture:
    if result.get("status") in {"REFUSED", "HUMAN_REVIEW"}:
        return DecisionPosture.WITHHOLD
    risk = str(result.get("threat_level") or "LOW").upper()
    if risk in {"HIGH", "CRITICAL"} or float(pressure.get("urgency", 0.0) or 0.0) > 0.70:
        return DecisionPosture.WARN
    if risk == "ELEVATED":
        return DecisionPosture.RECOMMEND
    return DecisionPosture.INFORM


def build_head_of_country_briefing(goal: Any, state_context: Any, result: Dict[str, Any], blackboard: Any = None) -> HeadOfStateBriefing:
    """Build a decision-maker briefing envelope from a pipeline result."""

    pressure_model = compute_strategic_pressure(state_context, result)
    pressure = pressure_model.model_dump()
    fuzzy_trace = build_fuzzy_trace(state_context, result)

    graph = StrategicKnowledgeGraph()
    graph.ingest_assessment(goal.country, state_context, result)

    threat = str(result.get("threat_level") or fuzzy_trace.get("risk_level") or "LOW").upper()
    pulse = pressure_model.pulse
    summary = (
        f"{goal.country} risk is {threat}. Strategic pulse is {pulse}. "
        f"Urgency={pressure_model.urgency:.2f}, uncertainty={pressure_model.uncertainty:.2f}, "
        f"diplomatic_window={pressure_model.diplomatic_window:.2f}."
    )

    findings = []
    for projected in fuzzy_trace.get("projected_signals", [])[:5]:
        if isinstance(projected, dict):
            signal = projected.get("signal_code") or projected.get("signal")
            confidence = projected.get("confidence")
            if signal and confidence is not None:
                findings.append(f"Fuzzy SRE driver: {signal} confidence={float(confidence):.2f}")
    for driver in pressure_model.drivers[:5]:
        findings.append(f"Signal driver: {driver}")
    if not findings:
        findings.append("No strong signal driver was available; treat assessment as collection-limited.")

    uncertainty = list(pressure_model.blindspots)
    if pressure_model.uncertainty >= 0.45:
        uncertainty.append("Confidence pressure is elevated; collect more independent corroboration.")
    if result.get("refusal"):
        uncertainty.append("Assessment gate withheld or limited the output.")

    red_team = []
    raw_red_team = result.get("red_team_report")
    if isinstance(raw_red_team, list):
        red_team.extend(str(item) for item in raw_red_team[:5])
    elif raw_red_team:
        red_team.append(str(raw_red_team))
    if not red_team:
        red_team.append("Challenge assumption that visible signals reflect intent rather than deterrent signaling.")

    learning_units: List[LearningUnit] = []
    if pressure_model.uncertainty >= 0.45:
        learning_units.append(
            LearningUnit(
                trace_id=goal.trace_id,
                topic="Reduce uncertainty in strategic pressure estimate",
                trigger="high_uncertainty",
                success_test="At least two independent sources corroborate the top signal drivers.",
                priority=pressure_model.uncertainty,
                evidence=pressure_model.blindspots,
            )
        )

    experiments = [
        ExperimentRecord(
            trace_id=goal.trace_id,
            hypothesis="Fuzzy SRE thresholds improve early-warning lead time without increasing false positives.",
            method="Run historical crisis replay and ablation suite before promotion.",
            metric="Brier score and lead-time days at HIGH threshold",
            success_threshold="Improves lead time or calibration by 5% without worse false positives.",
            rollback_rule="Keep existing thresholds if replay metrics regress.",
        )
    ]

    promotion = [
        PromotionStatus(
            candidate="nextgen_head_of_country_briefing",
            approved=True,
            evidence=["additive output envelope; no change to assessment gate"],
        )
    ]

    events = blackboard.history() if blackboard is not None and hasattr(blackboard, "history") else []

    return HeadOfStateBriefing(
        goal=goal,
        decision_posture=_posture_for_result(result, pressure),
        executive_summary=summary,
        evidence_findings=findings,
        options=_risk_options(threat, pressure),
        risk_matrix={
            "threat_level": threat,
            "pressure": pressure,
            "sre_domains": fuzzy_trace.get("sre_domains", {}),
            "sre_input": fuzzy_trace.get("sre_input", {}),
            "escalation_trace": fuzzy_trace.get("escalation_trace", []),
            "legal_firewall_rejections": fuzzy_trace.get("legal_firewall_rejections", []),
            "knowledge_graph": graph.to_dict(),
        },
        uncertainty=uncertainty,
        red_team_challenges=red_team,
        required_human_decisions=[
            "Confirm acceptable risk tolerance before any escalatory posture.",
            "Request legal/humanitarian review for any coercive or force-adjacent option.",
        ],
        next_collection_tasks=[
            "Corroborate top military/logistics indicators.",
            "Check diplomatic channel status and allied posture.",
            "Refresh economic pressure and domestic stability indicators.",
        ],
        fuzzy_trace=fuzzy_trace,
        blackboard_events=events,
        learning_units=learning_units,
        experiment_records=experiments,
        promotion_status=promotion,
    )
