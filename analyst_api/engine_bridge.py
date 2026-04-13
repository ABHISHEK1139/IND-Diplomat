"""
Engine Bridge — wraps the frozen diplomat_query() for async execution.
Extracts structured evidence, SRE, gate verdict, and verification chains.

STABILITY LOCK: This module calls the engine as a black box.
It does NOT modify any Layer 1-5 code.
"""

from __future__ import annotations

import asyncio
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Project root import fix ───────────────────────────────────────────
import sys
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from .job_store import job_store
from .models import (
    AssessmentRequest,
    AssessmentResult,
    CollectionDepth,
    CouncilSummary,
    EvidenceAtom,
    GateVerdictModel,
    JobPhase,
    MinisterReport,
    SREDecomposition,
    TemporalTrend,
    VerificationChain,
    VerificationStep,
)


# ── Collection depth → investigation loops ────────────────────────────

_DEPTH_MAP = {
    CollectionDepth.FAST:     1,
    CollectionDepth.STANDARD: 2,
    CollectionDepth.DEEP:     3,
}


def _run_diplomat_query_sync(request: AssessmentRequest, loops: int):
    """
    Execute the heavyweight assessment pipeline in a worker thread so the
    FastAPI event loop stays responsive to status polling.
    """
    from run import diplomat_query_sync

    return diplomat_query_sync(
        request.query,
        country_code=request.country_code,
        use_red_team=request.use_red_team,
        use_mcts=request.use_mcts,
        max_investigation_loops=loops,
    )


# ── Main entry point ─────────────────────────────────────────────────

async def run_assessment(job_id: str, request: AssessmentRequest) -> None:
    """
    Execute a full intelligence assessment as a background task.
    Updates job_store with phase transitions and final result.
    """
    try:
        # Phase 1: SCOPE_CHECK
        job_store.update_phase(job_id, JobPhase.SCOPE_CHECK,
                               "Validating question scope…", 10)

        # Phase 2: SENSORS
        job_store.update_phase(job_id, JobPhase.SENSORS,
                               "Collecting signals (GDELT + OSINT)…", 25)

        loops = _DEPTH_MAP.get(request.collection_depth, 2)
        start = time.perf_counter()

        result = await asyncio.to_thread(_run_diplomat_query_sync, request, loops)
        elapsed = time.perf_counter() - start

        # Phase 3: COUNCIL
        job_store.update_phase(job_id, JobPhase.COUNCIL,
                               "Council deliberation complete", 60)

        # Phase 4: GATE
        job_store.update_phase(job_id, JobPhase.GATE,
                               "Assessment gate evaluation", 80)

        # Phase 5: REPORT
        job_store.update_phase(job_id, JobPhase.REPORT,
                               "Building intelligence briefing…", 90)

        # Extract structured data from the raw PipelineResult
        raw = result._raw  # PipelineResult object
        council_dict = getattr(raw, "council_session", None) or {}
        gate_dict = getattr(raw, "gate_verdict", None) or {}

        # Build evidence chain
        evidence = extract_evidence_chain(raw, council_dict)

        # Build SRE decomposition
        sre = extract_sre(council_dict)

        # Build gate verdict model
        gate = extract_gate(gate_dict)

        # Build council summary
        council = extract_council(council_dict)

        # Build temporal trend info
        temporal = extract_temporal(council_dict)

        # Build verification/reasoning chain
        verification = extract_verification_chain(
            council_dict, gate_dict, raw
        )

        # Formatted report
        formatted_report = ""
        try:
            from engine.Layer5_Judgment.report_formatter import format_assessment
            report_dict = {
                "answer": result.answer,
                "outcome": result.outcome,
                "confidence": result.confidence,
                "risk_level": result.risk_level,
                "sources": result.sources,
                "operational_warnings": result.operational_warnings,
                "council_session": council_dict,
                "gate_verdict": gate_dict,
            }
            formatted_report = format_assessment(report_dict)
        except Exception:
            formatted_report = result.answer

        # Build trend data from monitor log
        trend_data = []
        try:
            from .trend_store import get_trends
            trend_data = get_trends(request.country_code, hours_back=72)
        except Exception:
            pass

        # Assemble final result
        whitebox_payload: Dict[str, Any] = {}
        try:
            whitebox_payload = dict(result.to_dict(whitebox=True).get("whitebox", {}) or {})
        except Exception:
            whitebox_payload = {}

        assessment = AssessmentResult(
            job_id=job_id,
            outcome=result.outcome,
            answer=result.answer,
            risk_level=result.risk_level or "",
            confidence=round(result.confidence, 4),
            analytic_confidence=round(getattr(raw, "analytic_confidence", 0.0), 4),
            epistemic_confidence=round(getattr(raw, "epistemic_confidence", 0.0), 4),
            early_warning_index=round(getattr(raw, "early_warning_index", 0.0), 4),
            sre=sre,
            gate_verdict=gate,
            council=council,
            temporal=temporal,
            evidence_chain=evidence,
            verification_chain=verification,
            trend_data=trend_data,
            formatted_report=formatted_report,
            operational_warnings=result.operational_warnings or [],
            whitebox=whitebox_payload,
            request=request,
        )

        job_store.complete_job(job_id, assessment)

    except Exception as exc:
        tb = traceback.format_exc()
        job_store.fail_job(job_id, f"{exc}\n{tb}")


# ── Evidence Extraction ──────────────────────────────────────────────

def extract_evidence_chain(raw: Any, council: Dict) -> List[EvidenceAtom]:
    """Walk sources + minister reports to build evidence provenance."""
    atoms: List[EvidenceAtom] = []
    seen = set()

    # From sources list on PipelineResult
    for src in (getattr(raw, "sources", None) or []):
        if isinstance(src, dict):
            key = src.get("title", "") or src.get("content", "")[:40]
            if key in seen:
                continue
            seen.add(key)
            atoms.append(EvidenceAtom(
                signal_name=src.get("title", "source"),
                source_type=src.get("source", "unknown"),
                source_detail=src.get("content", "")[:200],
                confidence=src.get("score", 0.0),
                timestamp=src.get("date", ""),
                dimension="",
                raw_snippet=src.get("content", "")[:300],
            ))

    # From minister reports — predicted signals
    ministers = council.get("minister_reports", {})
    for name, report in ministers.items():
        if not isinstance(report, dict):
            continue
        dim = report.get("dimension", "")
        conf = report.get("confidence", 0.0)
        cov = report.get("coverage", 0.0)
        for sig in report.get("predicted_signals", []):
            if sig in seen:
                continue
            seen.add(sig)
            atoms.append(EvidenceAtom(
                signal_name=sig,
                source_type=f"Minister:{name}",
                source_detail=f"coverage={cov:.2f}",
                confidence=conf,
                timestamp="",
                dimension=dim,
                raw_snippet=f"Predicted by {name} in {dim} dimension",
            ))

    return atoms


# ── SRE Extraction ───────────────────────────────────────────────────

def extract_sre(council: Dict) -> SREDecomposition:
    """Extract SRE domain breakdown from council_session."""
    domains = council.get("sre_domains", {})
    score = council.get("sre_escalation_score", 0.0)
    risk = council.get("risk_level", "UNKNOWN")

    cap = domains.get("capability", 0.0)
    intent = domains.get("intent", 0.0)
    stab = domains.get("stability", 0.0)
    cost = domains.get("cost", 0.0)

    # Reconstruct trend_bonus
    base = 0.35 * cap + 0.30 * intent + 0.20 * stab + 0.15 * cost
    trend_bonus = max(0.0, score - base)

    return SREDecomposition(
        capability=round(cap, 3),
        intent=round(intent, 3),
        stability=round(stab, 3),
        cost=round(cost, 3),
        trend_bonus=round(trend_bonus, 3),
        escalation_score=round(score, 3),
        risk_level=risk,
    )


# ── Gate Extraction ──────────────────────────────────────────────────

def extract_gate(gate: Dict) -> GateVerdictModel:
    """Extract gate verdict into typed model."""
    if not gate:
        return GateVerdictModel()
    return GateVerdictModel(
        approved=gate.get("approved", False),
        decision=gate.get("decision", "UNKNOWN"),
        reasons=gate.get("reasons", []),
        intelligence_gaps=gate.get("intelligence_gaps", []),
        collection_tasks=gate.get("collection_tasks", []),
        proposed_decision=gate.get("proposed_decision", ""),
        confidence=gate.get("confidence", 0.0),
    )


# ── Council Extraction ───────────────────────────────────────────────

def extract_council(council: Dict) -> CouncilSummary:
    """Extract council summary from session dict."""
    ministers = []
    for name, report in council.get("minister_reports", {}).items():
        if not isinstance(report, dict):
            continue
        ministers.append(MinisterReport(
            name=name,
            dimension=report.get("dimension", ""),
            confidence=report.get("confidence", 0.0),
            coverage=report.get("coverage", 0.0),
            predicted_signals=report.get("predicted_signals", []),
        ))

    return CouncilSummary(
        ministers=ministers,
        sensor_confidence=council.get("sensor_confidence", 0.0),
        document_confidence=council.get("document_confidence", 0.0),
        epistemic_confidence=council.get("epistemic_confidence", 0.0),
        analytic_confidence=council.get("analytic_confidence", 0.0),
        verification_score=council.get("verification_score", 0.0),
        grounding_passed=council.get("grounding_passed", False),
        evidence_atom_count=council.get("evidence_atom_count", 0),
        investigation_rounds=council.get("investigation_rounds", 0),
        hypotheses=council.get("hypotheses", []),
    )


# ── Temporal Extraction ──────────────────────────────────────────────

def extract_temporal(council: Dict) -> TemporalTrend:
    """Extract temporal trend info from council."""
    trend = council.get("temporal_trend", {})
    if not trend:
        return TemporalTrend()

    return TemporalTrend(
        snapshot_count=trend.get("snapshot_count", 0),
        escalation_patterns=trend.get("trend_override_count", 0),
        spikes=trend.get("spikes", 0),
        pattern_signals=trend.get("trend_overrides", []),
        indicators=trend.get("indicators", {}),
    )


# ── Verification Chain ───────────────────────────────────────────────

def extract_verification_chain(
    council: Dict,
    gate: Dict,
    raw: Any,
) -> VerificationChain:
    """
    Build the white-box reasoning chain:
    Observations → Beliefs → Ministers → Gate → Verdict
    """
    steps: List[VerificationStep] = []
    step_num = 0

    # Step 1: Observations (sensor data)
    step_num += 1
    sensor_conf = council.get("sensor_confidence", 0.0)
    doc_conf = council.get("document_confidence", 0.0)
    steps.append(VerificationStep(
        step=step_num,
        title="Signal Collection (Sensors)",
        description=f"GDELT + MoltBot sensors collected signals. "
                    f"Sensor confidence: {sensor_conf:.2f}, "
                    f"Document confidence: {doc_conf:.2f}",
        data={
            "sensor_confidence": sensor_conf,
            "document_confidence": doc_conf,
        },
    ))

    # Step 2: Belief Promotion
    step_num += 1
    atom_count = council.get("evidence_atom_count", 0)
    grounded = council.get("grounding_passed", False)
    steps.append(VerificationStep(
        step=step_num,
        title="Belief Promotion & Grounding",
        description=f"Accumulated {atom_count} evidence atoms. "
                    f"Grounding {'PASSED ✓' if grounded else 'FAILED ✗'}. "
                    f"Epistemic confidence: {council.get('epistemic_confidence', 0):.2f}",
        data={
            "evidence_atom_count": atom_count,
            "grounding_passed": grounded,
            "epistemic_confidence": council.get("epistemic_confidence", 0.0),
        },
    ))

    # Step 3: Minister Deliberation
    step_num += 1
    minister_data = {}
    for name, report in council.get("minister_reports", {}).items():
        if isinstance(report, dict):
            minister_data[name] = {
                "dimension": report.get("dimension", ""),
                "coverage": report.get("coverage", 0.0),
                "signals": report.get("predicted_signals", []),
            }
    steps.append(VerificationStep(
        step=step_num,
        title="Council of Ministers",
        description=f"{len(minister_data)} ministers deliberated across "
                    f"CAPABILITY, INTENT, STABILITY, COST dimensions. "
                    f"Analytic confidence: {council.get('analytic_confidence', 0):.2f}",
        data={"ministers": minister_data},
    ))

    # Step 4: SRE Computation
    step_num += 1
    sre_score = council.get("sre_escalation_score", 0.0)
    sre_domains = council.get("sre_domains", {})
    steps.append(VerificationStep(
        step=step_num,
        title="Strategic Risk Engine (SRE)",
        description=f"Escalation index: {sre_score:.3f}. "
                    f"Domains: cap={sre_domains.get('capability', 0):.2f}, "
                    f"int={sre_domains.get('intent', 0):.2f}, "
                    f"stab={sre_domains.get('stability', 0):.2f}, "
                    f"cost={sre_domains.get('cost', 0):.2f}",
        data={"sre_score": sre_score, "sre_domains": sre_domains},
    ))

    # Step 5: Temporal Analysis
    step_num += 1
    trend = council.get("temporal_trend", {})
    esc_patterns = trend.get("trend_override_count", 0)
    steps.append(VerificationStep(
        step=step_num,
        title="Temporal Memory Analysis",
        description=f"{trend.get('snapshot_count', 0)} historical snapshots analyzed. "
                    f"{esc_patterns} escalation pattern(s) detected. "
                    f"Overrides: {', '.join(trend.get('trend_overrides', [])[:5]) or 'none'}",
        data=trend,
    ))

    # Step 6: Assessment Gate
    step_num += 1
    gate_decision = gate.get("decision", "UNKNOWN")
    gate_approved = gate.get("approved", False)
    gate_reasons = gate.get("reasons", [])
    gaps = gate.get("intelligence_gaps", [])
    steps.append(VerificationStep(
        step=step_num,
        title="Assessment Gate",
        description=f"{'✅ APPROVED' if gate_approved else '🚫 WITHHELD'} — "
                    f"Decision: {gate_decision}. "
                    f"{'Gaps: ' + ', '.join(gaps[:3]) if gaps else 'No intelligence gaps.'}",
        data={
            "approved": gate_approved,
            "decision": gate_decision,
            "reasons": gate_reasons,
            "gaps": gaps,
        },
    ))

    # Step 7: Final Verdict
    step_num += 1
    risk = council.get("risk_level", getattr(raw, "risk_level", "UNKNOWN"))
    conf = council.get("analytic_confidence", getattr(raw, "confidence", 0.0))
    steps.append(VerificationStep(
        step=step_num,
        title="Final Verdict",
        description=f"Risk Level: {risk} | Confidence: {conf:.1%} | "
                    f"Escalation: {sre_score:.1%}",
        data={
            "risk_level": risk,
            "confidence": conf,
            "escalation_score": sre_score,
        },
    ))

    return VerificationChain(steps=steps, total_steps=len(steps))
