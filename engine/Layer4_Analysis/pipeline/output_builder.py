"""
Output Builder — WITHHELD / APPROVED response dict construction
================================================================
Extracted from coordinator.process_query output-building blocks.

Also houses serialisation helpers:
  - build_council_reasoning_dict
  - serialize_hypotheses
  - build_learning_block
  - build_global_model_block
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Serialisation helpers
# ═══════════════════════════════════════════════════════════════════


def build_council_reasoning_dict(session: Any) -> Dict[str, Any]:
    """Build council reasoning summary for output serialisation."""
    def _vote_counts(reports):
        votes = {"increase": 0, "decrease": 0, "maintain": 0}
        for r in (reports or []):
            adj = getattr(r, "risk_level_adjustment", "maintain") or "maintain"
            votes[adj] = votes.get(adj, 0) + 1
        return votes

    r1 = getattr(session, "round1_reports", []) or []
    r2 = getattr(session, "round2_reports", []) or []

    active_reports = r2 if r2 else r1
    all_drivers: list = []
    all_gaps: list = []
    for rpt in active_reports:
        all_drivers.extend(getattr(rpt, "primary_drivers", []) or [])
        all_gaps.extend(getattr(rpt, "critical_gaps", []) or [])

    return {
        "round1_votes": _vote_counts(r1),
        "round2_votes": _vote_counts(r2),
        "synthesis_summary": str(getattr(session, "synthesis_summary", "") or ""),
        "groupthink_flag": bool(getattr(session, "groupthink_flag", False)),
        "groupthink_penalty": round(float(getattr(session, "groupthink_penalty", 0.0) or 0.0), 4),
        "groupthink_reinvestigated": bool(getattr(session, "groupthink_reinvestigated", False)),
        "groupthink_reason": str(getattr(session, "groupthink_reason", "") or ""),
        "groupthink_context_gaps": list(getattr(session, "groupthink_context_gaps", []) or [])[:8],
        "council_adjustment": round(float(getattr(session, "council_adjustment", 0.0) or 0.0), 4),
        "minister_drivers": all_drivers[:10],
        "minister_gaps": all_gaps[:8],
        # ── Shadow-mode comparison metrics ─────────────────────
        "shadow_mode": bool(getattr(session, "shadow_mode_active", True)),
        "conf_without_council": round(float(getattr(session, "shadow_conf_without_council", 0.0) or 0.0), 6),
        "conf_with_council": round(float(getattr(session, "shadow_conf_with_council", 0.0) or 0.0), 6),
        "council_delta": round(float(getattr(session, "shadow_council_delta", 0.0) or 0.0), 6),
    }


def serialize_hypotheses(session: Any) -> List[Dict[str, Any]]:
    """Lightweight hypothesis export for logging/reporting."""
    serialized: List[Dict[str, Any]] = []
    hypotheses = list(getattr(session, "hypotheses", []) or [])
    for h in hypotheses:
        serialized.append({
            "hypothesis": str(getattr(h, "hypothesis", "") or ""),
            "dimension": getattr(h, "dimension", "UNKNOWN"),
            "matched_signals": sorted(list(getattr(h, "matched_signals", []) or [])),
            "missing_signals": list(getattr(h, "missing_signals", []) or []),
            "coverage": float(getattr(h, "coverage", 0.0) or 0.0),
            "weight": float(getattr(h, "weight", 1.0) or 1.0),
        })
    return serialized


def _minister_dimension(minister_name: str) -> str:
    """Map minister name → dimension string."""
    token = str(minister_name or "").lower()
    if "security" in token or "military" in token:
        return "CAPABILITY"
    if "diplomatic" in token or "alliance" in token or "strategy" in token:
        return "INTENT"
    if "domestic" in token:
        return "STABILITY"
    if "economic" in token:
        return "COST"
    return "UNKNOWN"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _serialize_minister_report(report: Any) -> Dict[str, Any]:
    name = str(getattr(report, "minister_name", "") or "")
    confidence = max(0.0, min(1.0, _safe_float(getattr(report, "confidence", 0.0), 0.0)))
    return {
        "confidence": confidence,
        "coverage": confidence,
        "dimension": _minister_dimension(name),
        "predicted_signals": list(getattr(report, "predicted_signals", []) or []),
        "classification_source": str(getattr(report, "classification_source", "") or ""),
        "reasoning_source": str(getattr(report, "reasoning_source", "") or ""),
        "classification_degraded": bool(getattr(report, "classification_degraded", False)),
        "reasoning_degraded": bool(getattr(report, "reasoning_degraded", False)),
        "degradation_reasons": list(getattr(report, "degradation_reasons", []) or []),
        "risk_level_adjustment": str(getattr(report, "risk_level_adjustment", "maintain") or "maintain"),
        "primary_drivers": list(getattr(report, "primary_drivers", []) or []),
        "critical_gaps": list(getattr(report, "critical_gaps", []) or []),
        "counterarguments": list(getattr(report, "counterarguments", []) or []),
        "confidence_modifier": _safe_float(getattr(report, "confidence_modifier", 0.0), 0.0),
        "justification_strength": _safe_float(getattr(report, "justification_strength", 0.5), 0.5),
        "reasoning_text": str(getattr(report, "reasoning_text", "") or ""),
        "effort_level": str(getattr(report, "effort_level", "medium") or "medium"),
        "self_critique_applied": bool(getattr(report, "self_critique_applied", False)),
        "self_critique_issues": list(getattr(report, "self_critique_issues", []) or []),
        "reasoning_quality_score": _safe_float(getattr(report, "reasoning_quality_score", 0.0), 0.0),
        "reasoning_signal_density": _safe_float(getattr(report, "reasoning_signal_density", 0.0), 0.0),
        "reasoning_length_ratio": _safe_float(getattr(report, "reasoning_length_ratio", 0.0), 0.0),
        "overthinking_detected": bool(getattr(report, "overthinking_detected", False)),
        "underthinking_detected": bool(getattr(report, "underthinking_detected", False)),
        "reasoning_monitor_issues": list(getattr(report, "reasoning_monitor_issues", []) or []),
        "classification_prompt": getattr(report, "classification_prompt", None),
        "classification_response": str(getattr(report, "classification_response", "") or ""),
        "reasoning_prompt": getattr(report, "reasoning_prompt", None),
        "reasoning_response": str(getattr(report, "reasoning_response", "") or ""),
        "reasoning_parsed": getattr(report, "reasoning_parsed", None),
        "classification_parsed": getattr(report, "classification_parsed", None),
    }


def _serialize_full_context(session: Any) -> Dict[str, Any]:
    full_context = getattr(session, "full_context", None)
    if full_context is None:
        return {}
    if hasattr(full_context, "to_dict"):
        try:
            payload = full_context.to_dict()
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
    if isinstance(full_context, dict):
        return dict(full_context)
    return {}


def _build_learning_block(session: Any) -> Dict[str, Any]:
    """Build the ``learning`` sub-dict for output."""
    return {
        "forecast_summary": dict(getattr(session, "learning_resolution", {}) or {}),
        "calibration": (
            (lambda: __import__("Layer6_Learning.calibration_engine", fromlist=["calibration_score"]).calibration_score(
                str(getattr(session, "learning_country", None) or "") or None
            ))() if True else {}
        ),
        "adjustments": (
            (lambda: __import__("Layer6_Learning.auto_adjuster", fromlist=["compute_adjustments"]).compute_adjustments())()
            if True else {}
        ),
        "confidence_multiplier": float(getattr(session, "learning_confidence_multiplier", 1.0) or 1.0),
        "drift": (
            (lambda: __import__("Layer6_Learning.auto_adjuster", fromlist=["get_drift_report"]).get_drift_report())()
            if True else {}
        ),
    }


def _build_global_model_block(session: Any) -> Dict[str, Any]:
    """Build the ``global_model`` sub-dict for output."""
    return {
        "theater_summary": {
            cc: {
                "sre": t.current_sre,
                "prob_high": t.prob_high_14d,
                "contagion": t.contagion_received,
            }
            for cc, t in __import__(
                "Layer7_GlobalModel.global_state", fromlist=["GLOBAL_THEATERS"]
            ).GLOBAL_THEATERS.items()
            if t.current_sre > 0.01
        }
        if True
        else {},
        "contagion": dict(getattr(session, "p7_contagion", {}) or {}),
        "adjusted_forecast": dict(getattr(session, "p7_adjusted_forecast", {}) or {}),
        "risk_summary": dict(getattr(session, "p7_risk_summary", {}) or {}),
        "systemic_cascade": bool(getattr(session, "p7_systemic_cascade", False)),
        "centrality": dict(getattr(session, "p7_centrality", {}) or {}),
        "collection_priority": list(getattr(session, "p7_collection_priority", []) or []),
        "conflict_state": dict(getattr(session, "conflict_state", {}) or {}),
        "gap_report": (
            getattr(session, "gap_report", None).to_dict()
            if getattr(session, "gap_report", None) is not None
            else None
        ),
        "uncertainty_explanation": str(getattr(session, "uncertainty_explanation", "") or ""),
        "council_reasoning": build_council_reasoning_dict(session),
    }


def _nullable_to_dict(obj: Any) -> Optional[Dict]:
    """Safe ``obj.to_dict()`` or None."""
    if obj is None:
        return None
    return obj.to_dict()


# ═══════════════════════════════════════════════════════════════════
# WITHHELD output builder
# ═══════════════════════════════════════════════════════════════════


def build_withheld_output(
    session: Any,
    gate_verdict: Any,
    final_sources: list,
    final_references: list,
    question: str = "",
) -> Dict[str, Any]:
    """Build the full WITHHELD return dict.

    Also fires the shadow log.
    """
    withheld_lines = [
        "ASSESSMENT WITHHELD",
        "=" * 60,
        "",
        "This system has determined that the available intelligence is",
        "INSUFFICIENT to support a reliable assessment.",
        "",
        f"Proposed assessment (NOT released): {gate_verdict.proposed_decision}",
        f"Analytic confidence: {gate_verdict.confidence:.3f}",
        "",
        "\u2500" * 60,
        "REASONS FOR WITHHOLDING:",
        "\u2500" * 60,
    ]
    for i, reason in enumerate(gate_verdict.reasons, 1):
        withheld_lines.append(f"  {i}. {reason}")

    if gate_verdict.required_collection:
        withheld_lines.extend([
            "",
            "\u2500" * 60,
            "PRIORITY INTELLIGENCE REQUIREMENTS (PIRs):",
            "\u2500" * 60,
        ])
        for i, req in enumerate(gate_verdict.required_collection, 1):
            withheld_lines.append(f"  PIR-{i}: {req}")

    if gate_verdict.intelligence_gaps:
        withheld_lines.extend([
            "",
            "\u2500" * 60,
            "INTELLIGENCE GAPS:",
            "\u2500" * 60,
        ])
        for gap in gate_verdict.intelligence_gaps:
            withheld_lines.append(f"  \u2022 {gap}")

    if gate_verdict.collection_tasks:
        withheld_lines.extend([
            "",
            "\u2500" * 60,
            "AUTO-COLLECTION TASKS (machine-readable):",
            "\u2500" * 60,
        ])
        for i, task in enumerate(gate_verdict.collection_tasks, 1):
            withheld_lines.append(
                f"  TASK-{i}: [{task.get('priority','?')}] "
                f"{task.get('signal','?')} via {task.get('modality','?')} "
                f"\u2014 {task.get('reason','')[:100]}"
            )

    withheld_lines.extend([
        "",
        "\u2500" * 60,
        "RECOMMENDATION: Collect the above intelligence before re-assessment.",
        "\u2500" * 60,
    ])
    withheld_answer = "\n".join(withheld_lines)
    logger.info("[GATE] Assessment WITHHELD \u2014 %d rules triggered", len(gate_verdict.reasons))

    # ── Shadow log ────────────────────────────────────────────────
    try:
        from engine.Layer4_Analysis.council_shadow_log import log_council_shadow as _shadow_log
        _shadow_log(session, gate_verdict.confidence, build_council_reasoning_dict(session), question=question)
    except Exception:
        pass

    council_reasoning = build_council_reasoning_dict(session)

    return {
        "answer": withheld_answer,
        "sources": final_sources,
        "references": final_references,
        "confidence": 0.0,
        "analytic_confidence": gate_verdict.confidence,
        "epistemic_confidence": float(getattr(session, "epistemic_confidence", 0.0) or 0.0),
        "risk_level": "WITHHELD",
        "early_warning_index": float(getattr(session, "early_warning_index", 0.0) or 0.0),
        "escalation_sync": float(getattr(session, "escalation_sync", 0.0) or 0.0),
        "prewar_detected": bool(getattr(session, "prewar_detected", False)),
        "warning": str(getattr(session, "warning", "") or ""),
        "status": "withheld",
        "sensor_confidence": float(getattr(session, "sensor_confidence", session.final_confidence) or 0.0),
        "document_confidence": float(getattr(session, "document_confidence", 0.0) or 0.0),
        "gate_verdict": gate_verdict.to_dict(),
        "council_session": {
            "session_id": session.session_id,
            "status": "WITHHELD",
            "phase_history": list(session.phase_history),
            "loop_count": session.loop_count,
            "gate_verdict": gate_verdict.to_dict(),
            "proposed_decision": gate_verdict.proposed_decision,
            "investigation_rounds": int(getattr(session, "investigation_rounds", 0) or 0),
            "investigation_closed": bool(getattr(session, "investigation_closed", False)),
            "minister_reports": {
                r.minister_name: _serialize_minister_report(r)
                for r in session.ministers_reports
            } if session.ministers_reports else {},
            "round1_reports": [_serialize_minister_report(r) for r in (getattr(session, "round1_reports", []) or [])],
            "round2_reports": [_serialize_minister_report(r) for r in (getattr(session, "round2_reports", []) or [])],
            "full_context": _serialize_full_context(session),
            "state_context": (
                session.state_context.to_dict() if hasattr(getattr(session, "state_context", None), "to_dict") else {}
            ),
            "hypotheses": serialize_hypotheses(session),
            "sensor_confidence": float(getattr(session, "sensor_confidence", session.final_confidence) or 0.0),
            "sre_escalation_score": float(getattr(session, "sre_escalation_score", 0.0) or 0.0),
            "sre_domains": dict(getattr(session, "sre_domains", {}) or {}),
            "red_team_report": dict(getattr(session, "red_team_report", {}) or {}),
            "red_team_confidence_penalty": float(getattr(session, "red_team_confidence_penalty", 0.0) or 0.0),
            "council_reasoning": council_reasoning,
            "trajectory": _nullable_to_dict(getattr(session, "trajectory_result", None)),
            "ndi": _nullable_to_dict(getattr(session, "ndi_result", None)),
            "black_swan": _nullable_to_dict(getattr(session, "black_swan_result", None)),
            "learning": _build_learning_block(session),
            "global_model": _build_global_model_block(session),
        },
    }


# ═══════════════════════════════════════════════════════════════════
# APPROVED output builder
# ═══════════════════════════════════════════════════════════════════


def build_approved_output(
    session: Any,
    analysis_result: Any,
    gate_verdict: Any,
    final_sources: list,
    final_references: list,
    escalation_trace: dict,
    verification_details: dict,
    needs_human_review: bool,
    country: str,
    question: str = "",
) -> Dict[str, Any]:
    """Build the full APPROVED return dict.

    Also fires the shadow log.
    """
    # ── Shadow log ────────────────────────────────────────────────
    try:
        from engine.Layer4_Analysis.council_shadow_log import log_council_shadow as _shadow_log
        _shadow_log(session, analysis_result.confidence_score, build_council_reasoning_dict(session), question=question)
    except Exception:
        pass

    council_reasoning = build_council_reasoning_dict(session)

    return {
        "answer": analysis_result.summary_text + "\n\n" + analysis_result.detailed_reasoning,
        "query": str(getattr(session, "question", "") or ""),
        "country": country,
        "sources": final_sources,
        "references": final_references,
        "confidence": analysis_result.confidence_score,
        "analytic_confidence": float(getattr(session, "sensor_confidence", session.final_confidence) or 0.0),
        "epistemic_confidence": float(getattr(session, "epistemic_confidence", 0.0) or 0.0),
        "risk_level": str(getattr(session, "king_decision", "UNKNOWN") or "UNKNOWN"),
        "early_warning_index": float(getattr(session, "early_warning_index", 0.0) or 0.0),
        "escalation_sync": float(getattr(session, "escalation_sync", 0.0) or 0.0),
        "prewar_detected": bool(getattr(session, "prewar_detected", False)),
        "warning": str(getattr(session, "warning", "") or ""),
        "status": str(getattr(session, "strategic_status", "stable") or "stable"),
        "sensor_confidence": float(getattr(session, "sensor_confidence", session.final_confidence) or 0.0),
        "document_confidence": float(getattr(session, "document_confidence", 0.0) or 0.0),
        "gate_verdict": gate_verdict.to_dict() if gate_verdict else None,
        "council_session": {
            "session_id": session.session_id,
            "query": str(getattr(session, "question", "") or ""),
            "country": country,
            "status": session.status.name,
            "phase_history": list(session.phase_history),
            "loop_count": session.loop_count,
            "black_swan": bool(session.black_swan),
            "prediction_enabled": bool(session.allow_prediction),
            "pressures": dict(getattr(session, "pressures", {}) or {}),
            "strategic_status": str(getattr(session, "strategic_status", "stable") or "stable"),
            "sensor_confidence": float(getattr(session, "sensor_confidence", session.final_confidence) or 0.0),
            "document_confidence": float(getattr(session, "document_confidence", 0.0) or 0.0),
            "minister_reports": {
                r.minister_name: _serialize_minister_report(r)
                for r in session.ministers_reports
            },
            "round1_reports": [_serialize_minister_report(r) for r in (getattr(session, "round1_reports", []) or [])],
            "round2_reports": [_serialize_minister_report(r) for r in (getattr(session, "round2_reports", []) or [])],
            "full_context": _serialize_full_context(session),
            "state_context": (
                session.state_context.to_dict() if hasattr(getattr(session, "state_context", None), "to_dict") else {}
            ),
            "verification_score": session.verification_score,
            "logic_score": float(getattr(session, "logic_score", 0.0) or 0.0),
            "evidence_atom_count": int(getattr(session, "evidence_atom_count", 0) or 0),
            "grounding_passed": bool(getattr(session, "grounding_passed", False)),
            "claim_support_passed": bool(getattr(session, "claim_support_passed", False)),
            "required_atoms_for_decision": int(getattr(session, "required_atoms_for_decision", 0) or 0),
            "epistemic_confidence": float(getattr(session, "epistemic_confidence", 0.0) or 0.0),
            "analytic_confidence": float(getattr(session, "sensor_confidence", session.final_confidence) or 0.0),
            "risk_level": str(getattr(session, "king_decision", "UNKNOWN") or "UNKNOWN"),
            "early_warning_index": float(getattr(session, "early_warning_index", 0.0) or 0.0),
            "escalation_sync": float(getattr(session, "escalation_sync", 0.0) or 0.0),
            "prewar_detected": bool(getattr(session, "prewar_detected", False)),
            "warning": str(getattr(session, "warning", "") or ""),
            "temporal_trend": dict(getattr(session, "temporal_trend", {}) or {}),
            "low_confidence_assessment": bool(getattr(session, "low_confidence_assessment", False)),
            "verification_details": verification_details,
            "needs_human_review": needs_human_review,
            "conflicts": session.identified_conflicts,
            "hypotheses": serialize_hypotheses(session),
            "investigation_rounds": int(getattr(session, "investigation_rounds", 0) or 0),
            "max_investigation_rounds": int(getattr(session, "MAX_INVESTIGATION_ROUNDS", 3) or 3),
            "investigation_cycles": int(getattr(session, "investigation_cycles", 0) or 0),
            "max_investigation_cycles": int(getattr(session, "MAX_INVESTIGATION_CYCLES", 3) or 3),
            "investigation_closed": bool(getattr(session, "investigation_closed", False)),
            "citation_count": int((analysis_result.metadata or {}).get("citation_count", 0) or 0),
            "escalation_trace": escalation_trace,
            "sre_escalation_score": float(getattr(session, "sre_escalation_score", 0.0) or 0.0),
            "sre_domains": dict(getattr(session, "sre_domains", {}) or {}),
            "trajectory": _nullable_to_dict(getattr(session, "trajectory_result", None)),
            "ndi": _nullable_to_dict(getattr(session, "ndi_result", None)),
            "black_swan": _nullable_to_dict(getattr(session, "black_swan_result", None)),
            "meta_confidence": float(
                getattr(getattr(session.state_context, "meta", None), "data_confidence", 0.5) or 0.5
            ) if hasattr(session, "state_context") else 0.5,
            "projected_signals": dict(
                getattr(session.state_context, "projected_signals", {}) or {}
            ) if hasattr(session, "state_context") else {},
            "signal_count": len(
                getattr(session.state_context, "projected_signals", {}) or {}
            ) if hasattr(session, "state_context") else 0,
            "matched_signals": sorted({
                sig for h in list(getattr(session, "hypotheses", []) or [])
                for sig in list(getattr(h, "matched_signals", []) or [])
            }),
            "missing_signals": list(getattr(session, "missing_signals", []) or []),
            "evidence_log": list(getattr(session, "evidence_log", []) or [])[:50],
            "rag_evidence": [
                {
                    "source": str(r.get("source", "")),
                    "excerpt": str(r.get("excerpt", ""))[:500],
                    "confidence": float(r.get("confidence", r.get("rag_relevance", 0.0)) or 0.0),
                    "treaty_name": str(r.get("treaty_name", "")),
                    "article_number": str(r.get("article_number", "")),
                    "domain": str(r.get("domain", "")),
                    "year": str(r.get("year", "")),
                    "heading": str(r.get("heading", "")),
                    "country": str(r.get("country", "")),
                    "chunk_type": str(r.get("chunk_type", "")),
                }
                for r in (getattr(session, "rag_evidence", []) or [])
                if isinstance(r, dict)
            ],
            "gate_verdict": gate_verdict.to_dict() if gate_verdict else None,
            "red_team_report": dict(getattr(session, "red_team_report", {}) or {}),
            "red_team_confidence_penalty": float(getattr(session, "red_team_confidence_penalty", 0.0) or 0.0),
            "council_reasoning": council_reasoning,
            "debate_result": dict(getattr(session, "debate_result", {}) or {}),
            "curiosity_plan": (
                getattr(session, "curiosity_plan", None).to_dict()
                if hasattr(getattr(session, "curiosity_plan", None), "to_dict")
                else dict(getattr(session, "curiosity_plan", {}) or {})
            ),
            "learning": _build_learning_block(session),
            "global_model": _build_global_model_block(session),
        },
    }
