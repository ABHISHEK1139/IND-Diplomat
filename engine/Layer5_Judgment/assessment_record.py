"""
Layer-5 Assessment Record — The Flight Recorder
=================================================

Freezes every piece of intelligence cognition into a single immutable
JSON document (``assessment_record.json``) that Layer-6 reads.

Design rule
-----------
Layer-5 **writes** this record.  Layer-6 **reads** it.
Layer-6 never computes intelligence — it is a camera, not a narrator.

The record has 9 sections:

    1. metadata         — session id, timestamp, query, country
    2. observations      — sensor scores, projected signals, matched signals
    3. beliefs           — hypotheses with per-dimension coverage
    4. risk_engine       — threat level, confidence breakdown, temporal trend
    5. council_debate    — minister positions, conflicts, consensus, synthesis
    6. red_team          — challenge results, contradictions, penalty
    7. legal_analysis    — RAG evidence, treaty references, legal constraints
    8. intelligence_gaps — PIRs, missing signals, curiosity targets
    9. final_assessment  — gate verdict, key judgments, recommendations
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Layer5_Judgment.assessment_record")

# Default directory for frozen records
_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "assessments"


# =====================================================================
# Section builders — each takes the pipeline result dict and extracts
# exactly what belongs in its section.  Pure functions, no side effects.
# =====================================================================

def _build_metadata(result: Dict[str, Any]) -> Dict[str, Any]:
    cs = result.get("council_session", {})
    return {
        "session_id": cs.get("session_id", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": result.get("query", cs.get("query", "")),
        "country": cs.get("country", result.get("country", "")),
        "pipeline_version": "DIP_3.2",
        "status": cs.get("status", "UNKNOWN"),
    }


def _build_observations(result: Dict[str, Any]) -> Dict[str, Any]:
    cs = result.get("council_session", {})
    # Aggregate matched/missing signals from serialized hypotheses
    all_matched: List[str] = []
    all_predicted: List[str] = []
    for h in cs.get("hypotheses", []):
        if isinstance(h, dict):
            all_matched.extend(h.get("matched_signals", []))
            all_predicted.extend(h.get("predicted_signals", []))

    # Phase 8: robust signal_count — try explicit key, then projected
    # signals dict length, then count of unique predicted signals.
    _sig_count = cs.get("signal_count", 0)
    if not _sig_count:
        _proj = cs.get("projected_signals", {})
        _sig_count = len(_proj) if _proj else len(set(all_predicted))

    return {
        "sensor_score": cs.get("sensor_confidence", 0.0),
        "signal_count": _sig_count,
        "stale_signals": cs.get("stale_signals", []),
        "projected_signals": cs.get("projected_signals", {}),
        "matched_signals": sorted(set(all_matched)) if all_matched else cs.get("matched_signals", []),
        "evidence_log_size": len(cs.get("evidence_log", []) or []),
    }


def _build_beliefs(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    hypotheses = result.get("council_session", {}).get("hypotheses", [])
    beliefs = []
    for h in hypotheses:
        if isinstance(h, dict):
            beliefs.append({
                "minister": h.get("minister", ""),
                "dimension": h.get("dimension", ""),
                "predicted_signals": h.get("predicted_signals", []),
                "matched_signals": h.get("matched_signals", []),
                "missing_signals": h.get("missing_signals", []),
                "coverage": h.get("coverage", 0.0),
                "weight": h.get("weight", 1.0),
            })
    return beliefs


def _build_risk_engine(result: Dict[str, Any]) -> Dict[str, Any]:
    cs = result.get("council_session", {})
    return {
        "threat_level": cs.get("risk_level", "UNKNOWN"),
        "final_confidence": cs.get("analytic_confidence", cs.get("sensor_confidence", 0.0)),
        "confidence_breakdown": {
            "sensor_confidence": cs.get("sensor_confidence", 0.0),
            "document_confidence": cs.get("document_confidence", 0.0),
            "verification_score": cs.get("verification_score", 0.0),
            "logic_score": cs.get("logic_score", 0.0),
            "meta_confidence": cs.get("meta_confidence", 0.0),
        },
        "red_team_confidence_penalty": cs.get("red_team_confidence_penalty", 0.0),
        "temporal_trend": cs.get("temporal_trend", {}),
        "warning": cs.get("warning", ""),
        "sre_escalation_score": cs.get("sre_escalation_score", 0.0),
        "sre_domains": cs.get("sre_domains", {}),
        "low_confidence_assessment": cs.get("low_confidence_assessment", False),
    }


def _build_council_debate(result: Dict[str, Any]) -> Dict[str, Any]:
    cs = result.get("council_session", {})
    debate = cs.get("debate_result", {}) or {}
    # minister_reports is a dict keyed by minister name
    ministers = cs.get("minister_reports", {}) or {}
    positions = []
    if isinstance(ministers, dict):
        for name, data in ministers.items():
            if isinstance(data, dict):
                positions.append({
                    "minister": name,
                    "predicted_signals": data.get("predicted_signals", []),
                    "confidence": data.get("confidence", 0.0),
                    "dimension": data.get("dimension", ""),
                    "coverage": data.get("coverage", 0.0),
                })
    elif isinstance(ministers, list):
        # Fallback for legacy list-of-dicts format
        for m in ministers:
            if isinstance(m, dict):
                positions.append({
                    "minister": m.get("minister_name", m.get("minister", "")),
                    "predicted_signals": m.get("predicted_signals", []),
                    "confidence": m.get("confidence", 0.0),
                    "dimension": m.get("dimension", ""),
                    "coverage": m.get("coverage", 0.0),
                })
    return {
        "minister_positions": positions,
        "conflicts": cs.get("conflicts", []) or [],
        "debate_outcome": debate.get("outcome", ""),
        "consensus_points": debate.get("consensus_points", []) or [],
        "conflicts_surfaced": debate.get("conflicts_surfaced", []) or [],
        "synthesis": debate.get("synthesis", ""),
        "debate_confidence": debate.get("confidence", 0.0),
        "council_reasoning": cs.get("council_reasoning", {}),
    }


def _build_red_team(result: Dict[str, Any]) -> Dict[str, Any]:
    cs = result.get("council_session", {})
    rt = cs.get("red_team_report", {}) or {}
    return {
        "active": rt.get("active", False),
        "agent": rt.get("agent", "none"),
        "is_robust": rt.get("is_robust", True),
        "challenged_hypotheses": rt.get("challenged_hypotheses", 0),
        "contradictions": rt.get("contradictions", []) or [],
        "critique": rt.get("critique", ""),
        "counter_evidence": rt.get("counter_evidence", []) or [],
        "confidence_penalty": cs.get("red_team_confidence_penalty", 0.0),
    }


def _build_legal_analysis(result: Dict[str, Any]) -> Dict[str, Any]:
    cs = result.get("council_session", {})
    rag = cs.get("rag_evidence", []) or []
    # Group by domain
    treaties = []
    for r in rag:
        if isinstance(r, dict):
            treaties.append({
                "source": r.get("source", ""),
                "treaty_name": r.get("treaty_name", ""),
                "article_number": r.get("article_number", ""),
                "domain": r.get("domain", ""),
                "year": r.get("year", ""),
                "heading": r.get("heading", ""),
                "country": r.get("country", ""),
                "chunk_type": r.get("chunk_type", ""),
                "excerpt": r.get("excerpt", ""),
                "confidence": r.get("confidence", 0.0),
            })

    # ── Legal Constraint Analysis (LLM-reasoned, post-gate) ──────
    # This comes from the new legal_reasoner + legal_output_validator
    # pipeline.  It produces a structured "prohibited/permitted/
    # conditional" analysis rather than raw treaty excerpts.
    legal_constraint_data = cs.get("legal_constraint_analysis", {}) or {}
    legal_constraints = legal_constraint_data.get("validated_constraints", [])
    hallucinations_blocked = legal_constraint_data.get("hallucinations_blocked", 0)
    llm_used = legal_constraint_data.get("llm_used", False)
    legal_error = legal_constraint_data.get("error")

    # Evidence items (structured) from the formatter
    evidence_items_raw = cs.get("legal_evidence_items", []) or []
    evidence_items = []
    for item in evidence_items_raw:
        if isinstance(item, dict):
            evidence_items.append(item)

    return {
        "treaty_references": treaties,
        "total_legal_sources": len(treaties),
        "domains_covered": list({t["domain"] for t in treaties if t.get("domain")}),
        # New: structured legal constraint analysis
        "legal_constraints": legal_constraints,
        "hallucinations_blocked": hallucinations_blocked,
        "llm_reasoning_used": llm_used,
        "llm_reasoning_error": legal_error,
        "evidence_items": evidence_items,
    }


def _build_intelligence_gaps(result: Dict[str, Any]) -> Dict[str, Any]:
    cs = result.get("council_session", {})
    curiosity = cs.get("curiosity_plan", {}) or {}
    gate = cs.get("gate_verdict", {}) or {}
    # Aggregate missing signals from hypotheses if not at top-level
    missing = cs.get("missing_signals", []) or []
    if not missing:
        for h in cs.get("hypotheses", []):
            if isinstance(h, dict):
                missing.extend(h.get("missing_signals", []))
        missing = sorted(set(missing))
    return {
        "missing_signals": missing,
        "intelligence_gaps": gate.get("intelligence_gaps", []) or [],
        "required_collection": gate.get("required_collection", []) or [],
        "curiosity_targets": curiosity.get("targets", []) or [],
        "pir_count": curiosity.get("target_count", curiosity.get("pir_count", 0))
                     or len(gate.get("required_collection", []) or []),  # Phase 8: fallback to collection tasks
        "critical_pirs": curiosity.get("above_threshold", curiosity.get("critical_count", 0)),
    }


def _build_final_assessment(result: Dict[str, Any]) -> Dict[str, Any]:
    cs = result.get("council_session", {})
    gate = cs.get("gate_verdict", {}) or {}

    # Build key judgments from available data
    key_judgments = []
    decision = cs.get("risk_level", "UNKNOWN")
    confidence = cs.get("analytic_confidence", cs.get("sensor_confidence", 0.0))
    warning = cs.get("warning", "")

    key_judgments.append({
        "judgment": f"Assessed threat level: {decision} (confidence: {confidence:.1%})",
        "basis": "Multi-source sensor fusion + minister council synthesis",
        "confidence": confidence,
    })

    if warning:
        key_judgments.append({
            "judgment": warning,
            "basis": "Temporal trend analysis and early warning indicators",
            "confidence": confidence,
        })

    # Red team impact judgment
    rt_penalty = cs.get("red_team_confidence_penalty", 0.0)
    if rt_penalty > 0:
        key_judgments.append({
            "judgment": f"Confidence reduced by {rt_penalty:.1%} due to red team challenge",
            "basis": "Red team found assessment not robust",
            "confidence": confidence,
        })

    # Gate status
    if gate.get("withheld"):
        key_judgments.append({
            "judgment": "ASSESSMENT WITHHELD — insufficient intelligence basis",
            "basis": "; ".join(gate.get("reasons", [])),
            "confidence": 0.0,
        })

    return {
        "gate_approved": gate.get("approved", False),
        "gate_decision": gate.get("decision", "WITHHELD"),
        "gate_reasons": gate.get("reasons", []),
        "key_judgments": key_judgments,
        "recommendation": cs.get("recommendation", ""),
        "needs_human_review": cs.get("needs_human_review", False),
    }


# =====================================================================
# Public API
# =====================================================================

def build_assessment_record(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assemble the complete 9-section assessment record from a pipeline
    result dict.

    Parameters
    ----------
    result : dict
        The full dictionary returned by ``Coordinator.process_query()``.

    Returns
    -------
    dict
        The frozen assessment record ready for JSON serialization.
    """
    return {
        "metadata": _build_metadata(result),
        "observations": _build_observations(result),
        "beliefs": _build_beliefs(result),
        "risk_engine": _build_risk_engine(result),
        "council_debate": _build_council_debate(result),
        "red_team": _build_red_team(result),
        "legal_analysis": _build_legal_analysis(result),
        "intelligence_gaps": _build_intelligence_gaps(result),
        "final_assessment": _build_final_assessment(result),
    }


def write_assessment_record(
    result: Dict[str, Any],
    output_dir: Optional[str] = None,
) -> Path:
    """
    Build the record and write it to disk as JSON.

    Parameters
    ----------
    result : dict
        Pipeline result from ``Coordinator.process_query()``.
    output_dir : str, optional
        Directory to write into.  Defaults to ``<project>/assessments/``.

    Returns
    -------
    Path
        The path to the written JSON file.
    """
    record = build_assessment_record(result)

    out = Path(output_dir) if output_dir else _DEFAULT_DIR
    out.mkdir(parents=True, exist_ok=True)

    session_id = record["metadata"]["session_id"]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"assessment_{session_id}_{ts}.json"
    filepath = out / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False, default=str)

    logger.info("Assessment record written → %s", filepath)
    return filepath
