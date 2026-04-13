"""
Layer-6 Presentation — Report Builder
=======================================

Transforms internal pipeline state into a human-readable intelligence
briefing.  The analyst brain (Layers 1-5) thinks.  This layer *speaks*.

Entry point:
    build_user_report(result_dict, gate_verdict=None) -> str

``result_dict`` is the raw dict returned by ``CouncilCoordinator.process_query()``
(also accessible as ``DiplomatResult._raw`` fields).

``gate_verdict`` is the optional ``GateVerdict.to_dict()`` output
from ``Layer5_Judgment.assessment_gate``.  If the coordinator already
embedded it in the result under ``gate_verdict``, the builder extracts
it automatically.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from engine.Layer6_Presentation.report_templates import (
    AUTHORIZED_TEMPLATE,
    DIMENSION_LABELS,
    HEADER,
    HEAVY_LINE,
    LIGHT_LINE,
    WITHHELD_TEMPLATE,
    confidence_word,
    dimension_word,
)

logger = logging.getLogger("Layer6_Presentation.report_builder")


# =====================================================================
# Internal helpers
# =====================================================================

def _s(value: Any, default: str = "") -> str:
    """Safe string coercion."""
    return str(value or default) if value is not None else default


def _f(value: Any, default: float = 0.0) -> float:
    """Safe float coercion."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_gate(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pull gate_verdict from the result dict if present."""
    gate = result.get("gate_verdict")
    if isinstance(gate, dict):
        return gate
    cs = result.get("council_session")
    if isinstance(cs, dict):
        gate = cs.get("gate_verdict")
        if isinstance(gate, dict):
            return gate
    return None


def _extract_dimensions(result: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract dimension coverages from multiple sources.

    Priority order:
    1. Answer text [DIMENSIONS] line (authorized assessments)
    2. council_session.minister_reports (full session)
    3. intelligence_report.situation_overview parsing
    """
    dims = {"CAPABILITY": 0.0, "INTENT": 0.0, "STABILITY": 0.0, "COST": 0.0}

    # Try parsing from the answer text
    answer = _s(result.get("answer", ""))
    for line in answer.splitlines():
        if "[DIMENSIONS]" in line:
            for token in line.split(","):
                token = token.strip()
                for dim in dims:
                    if dim + "=" in token:
                        try:
                            val = float(token.split("=")[1].strip())
                            dims[dim] = val
                        except (ValueError, IndexError):
                            pass
            break

    # Fallback: council_session minister_reports
    if all(v == 0.0 for v in dims.values()):
        cs = result.get("council_session", {}) or {}
        ministers = cs.get("minister_reports", {}) or {}
        # Primary: use the "dimension" field stored by coordinator
        for name, info in ministers.items():
            info = info or {}
            dim = _s(info.get("dimension", "")).upper()
            if dim in dims:
                dims[dim] = max(dims[dim], _f(info.get("coverage", info.get("confidence", 0.0))))
        # Secondary: name-based mapping if dimension field missing
        if all(v == 0.0 for v in dims.values()):
            dim_map = {
                "Security Minister": "CAPABILITY",
                "Economic Minister": "COST",
                "Domestic Minister": "STABILITY",
                "Diplomatic Minister": "INTENT",
            }
            for name, dim in dim_map.items():
                info = ministers.get(name, {}) or {}
                dims[dim] = max(dims[dim], _f(info.get("coverage", 0.0)))

    # Fallback: gate_verdict embedded state (WITHHELD path)
    if all(v == 0.0 for v in dims.values()):
        gate = _extract_gate(result) or {}
        # The coordinator's WITHHELD council_session includes proposed_decision
        # but for dimensions we need to look at the original answer before override.
        # Parse from the intelligence_report situation_overview instead.
        ir = result.get("intelligence_report") or {}
        overview = _s(ir.get("situation_overview", ""))
        # situation_overview contains lines like "Military posture: mobilization index 0.51"
        # but more reliably, the key_indicators list has the signal names
        # Let's use evidence_sources to estimate dimension coverage
        evidence = ir.get("evidence_sources") or []
        econ_signals = {"SIG_ECON_PRESSURE", "SIG_ECONOMIC_PRESSURE", "SIG_ECO_SANCTIONS_ACTIVE",
                        "SIG_ECO_PRESSURE_HIGH", "SIG_SANCTIONS_ACTIVE"}
        mil_signals = {"SIG_MIL_ESCALATION", "SIG_FORCE_POSTURE", "SIG_MIL_MOBILIZATION"}
        stab_signals = {"SIG_INTERNAL_INSTABILITY", "SIG_DECEPTION_ACTIVITY", "SIG_DOM_INTERNAL_INSTABILITY",
                        "SIG_PUBLIC_PROTEST", "SIG_ELITE_FRACTURE", "SIG_MILITARY_DEFECTION"}
        intent_signals = {"SIG_ALLIANCE_ACTIVATION", "SIG_ALLIANCE_SHIFT", "SIG_DIP_HOSTILITY",
                          "SIG_COERCIVE_PRESSURE", "SIG_NEGOTIATION_BREAKDOWN"}

        found_signals = set()
        for ev in evidence:
            sig = _s(ev.get("signal", "")).upper()
            if sig:
                found_signals.add(sig)

        # Count how many signals we have per dimension as rough coverage
        for sig_set, dim in [(mil_signals, "CAPABILITY"), (econ_signals, "COST"),
                             (stab_signals, "STABILITY"), (intent_signals, "INTENT")]:
            hits = len(found_signals & sig_set)
            total = max(len(sig_set), 1)
            dims[dim] = max(dims[dim], hits / total)

    return dims


def _extract_weak_signals(result: Dict[str, Any]) -> List[str]:
    """Extract weak signals from multiple sources."""
    # 1. Answer text [WEAK_SIGNALS] line
    answer = _s(result.get("answer", ""))
    for line in answer.splitlines():
        if "[WEAK_SIGNALS]" in line:
            after = line.split("]", 1)[-1].strip()
            signals = [s.strip() for s in after.split(",") if s.strip()]
            if signals:
                return signals

    # 2. Minister predicted_signals from council_session
    cs = result.get("council_session", {}) or {}
    ministers = cs.get("minister_reports", {}) or {}
    predicted = set()
    for name, info in ministers.items():
        for sig in (info.get("predicted_signals") or []):
            predicted.add(sig)

    # 3. intelligence_report key_indicators
    ir = result.get("intelligence_report") or {}
    key_ind = ir.get("key_indicators") or []
    for ind in key_ind:
        s_val = _s(ind).upper()
        if s_val.startswith("SIG_"):
            predicted.add(s_val)

    return sorted(predicted)


def _extract_sources(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get sources list from result."""
    sources = result.get("sources") or []
    if not sources:
        ir = result.get("intelligence_report") or {}
        sources = ir.get("evidence_sources") or []
    return sources[:12]


def _format_dimensions(dims: Dict[str, float]) -> str:
    """Format dimensions into a human-readable situation picture."""
    lines = []
    for dim_key in ["CAPABILITY", "INTENT", "STABILITY", "COST"]:
        val = dims.get(dim_key, 0.0)
        label = DIMENSION_LABELS.get(dim_key, dim_key)
        word = dimension_word(val)
        bar_len = int(val * 20)
        bar = "\u2588" * bar_len + "\u2591" * (20 - bar_len)
        lines.append(f"  {label:<25s} {bar} {word} ({val:.0%})")
    return "\n".join(lines)


def _format_sources(sources: List[Dict[str, Any]]) -> str:
    """Format sources into numbered list."""
    if not sources:
        return "  (no sources available)"
    lines = []
    seen = set()
    for src in sources:
        name = _s(src.get("source", src.get("id", "?")))
        url = _s(src.get("url", ""))
        key = (name, url)
        if key in seen:
            continue
        seen.add(key)
        date = _s(src.get("date", ""))
        score = _f(src.get("score", src.get("reliability", 0)))
        line = f"  • {name}"
        if date:
            line += f"  ({date})"
        if score > 0:
            line += f"  [reliability: {score:.0%}]"
        if url:
            line += f"\n    {url}"
        lines.append(line)
    return "\n".join(lines) if lines else "  (no sources available)"


def _format_gaps(gaps: List[str]) -> str:
    """Format intelligence gaps."""
    if not gaps:
        return "  None identified."
    # Map signal codes to human-readable descriptions
    signal_descriptions = {
        "SIG_MIL_ESCALATION": "military escalation indicators",
        "SIG_FORCE_POSTURE": "force posture / troop deployments",
        "SIG_MIL_MOBILIZATION": "military mobilization activity",
        "SIG_LOGISTICS_PREP": "logistics and supply chain preparation",
        "SIG_LOGISTICS_SURGE": "logistics surge indicators",
        "SIG_CYBER_ACTIVITY": "cyber operation indicators",
        "SIG_INTERNAL_INSTABILITY": "domestic unrest / internal stability",
        "SIG_PUBLIC_PROTEST": "public protests / civil demonstrations",
        "SIG_ELITE_FRACTURE": "elite power struggle / regime fracture",
        "SIG_MILITARY_DEFECTION": "military defection / coup indicators",
        "SIG_DECEPTION_ACTIVITY": "deception and denial activity",
        "SIG_WMD_RISK": "weapons of mass destruction indicators",
        "SIG_DIP_HOSTILITY": "diplomatic hostility level",
        "SIG_ALLIANCE_ACTIVATION": "alliance activation signals",
        "SIG_ALLIANCE_SHIFT": "alliance realignment",
        "SIG_NEGOTIATION_BREAKDOWN": "negotiation breakdown",
    }
    lines = []
    for gap in gaps:
        human = signal_descriptions.get(gap.upper(), gap)
        lines.append(f"  • {human}")
    return "\n".join(lines)


def _format_collection(pirs: List[str]) -> str:
    """Format PIR collection requirements into actionable language."""
    if not pirs:
        return "  No specific collection requirements."

    # Map modality keywords to human descriptions
    modality_descriptions = {
        "SIPRI_ARMS": "arms transfer tracking (SIPRI databases)",
        "IMINT": "satellite / imagery intelligence (IMINT)",
        "TRADE_FLOW": "trade flow and logistics monitoring",
        "CYBER_INTEL": "cyber incident and threat monitoring",
        "OSINT_SOCIAL": "open-source social media intelligence",
        "SIGINT": "signals intelligence intercepts",
        "HUMINT": "human intelligence sources",
        "FININT": "financial intelligence tracking",
    }

    lines = []
    seen_modalities = set()
    for pir_text in pirs:
        # Extract modality from PIR text like "SIG_X via IMINT [CRITICAL]"
        if " via " in pir_text:
            parts = pir_text.split(" via ", 1)
            modality_part = parts[1].split("[")[0].strip() if len(parts) > 1 else ""
            if modality_part and modality_part not in seen_modalities:
                seen_modalities.add(modality_part)
                human = modality_descriptions.get(modality_part, modality_part)
                lines.append(f"  → {human}")
        elif pir_text.startswith("Missing:"):
            sig = pir_text.replace("Missing:", "").strip()
            # Already covered in gaps section
            continue
        elif pir_text.startswith("Stale:"):
            sig_part = pir_text.replace("Stale:", "").strip()
            lines.append(f"  → UPDATE NEEDED: {sig_part}")

    if not lines:
        # Fallback: just list the first few PIRs as-is
        for pir_text in pirs[:6]:
            lines.append(f"  → {pir_text[:80]}")

    return "\n".join(lines) if lines else "  No specific collection requirements."


def _format_indicators(weak_signals: List[str], dims: Dict[str, float]) -> str:
    """Format early-warning indicators — what would change the picture."""
    lines = []

    # From weak signals
    indicator_map = {
        "SIG_MIL_ESCALATION": "confirmed military mobilization or deployment",
        "SIG_FORCE_POSTURE": "verified troop movements or airbase activation",
        "SIG_MIL_MOBILIZATION": "emergency reserve call-ups",
        "SIG_LOGISTICS_PREP": "supply chain surge or pre-positioning",
        "SIG_CYBER_ACTIVITY": "coordinated cyber operations against infrastructure",
        "SIG_INTERNAL_INSTABILITY": "significant domestic unrest or regime instability",
        "SIG_PUBLIC_PROTEST": "mass public protests or civil unrest (low escalation relevance)",
        "SIG_ELITE_FRACTURE": "elite power struggle, leadership purge, or factional split",
        "SIG_MILITARY_DEFECTION": "military defection, mutiny, or coup attempt — critical warning",
        "SIG_DECEPTION_ACTIVITY": "detected denial and deception operations",
        "SIG_DIP_HOSTILITY": "embassy closures or diplomatic expulsions",
        "SIG_ALLIANCE_ACTIVATION": "mutual defense treaty activation",
        "SIG_WMD_RISK": "WMD-related activity detected",
        "SIG_NEGOTIATION_BREAKDOWN": "collapse of ongoing negotiations",
    }

    for sig in weak_signals:
        human = indicator_map.get(sig.upper())
        if human:
            lines.append(f"  ▸ {human}")

    # From dimension gaps
    if dims.get("CAPABILITY", 0) < 0.35:
        if "confirmed military mobilization or deployment" not in [l.strip("  ▸ ") for l in lines]:
            lines.append("  ▸ any verified military capability indicator")
    if dims.get("INTENT", 0) < 0.35:
        lines.append("  ▸ shift in diplomatic posture or alliance behavior")

    if not lines:
        lines.append("  ▸ significant change in any dimension coverage above 50%")

    return "\n".join(lines)


# =====================================================================
# Main entry point
# =====================================================================

def build_user_report(
    result: Dict[str, Any],
    gate_verdict: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build a human-readable intelligence briefing from pipeline output.

    Parameters
    ----------
    result : dict
        The raw dict from ``CouncilCoordinator.process_query()`` or
        the fields accessible on ``PipelineResult``.
    gate_verdict : dict, optional
        The ``GateVerdict.to_dict()`` output.  If None, extracted from
        ``result["gate_verdict"]`` if present.

    Returns
    -------
    str
        A formatted intelligence briefing suitable for end-user display.
    """
    # Extract gate verdict
    gate = gate_verdict or _extract_gate(result)
    is_withheld = (gate or {}).get("withheld", False)

    # If risk_level is WITHHELD but no gate dict, treat as withheld
    if not is_withheld and _s(result.get("risk_level")).upper() == "WITHHELD":
        is_withheld = True

    # Common extractions
    dims = _extract_dimensions(result)
    weak_signals = _extract_weak_signals(result)
    sources = _extract_sources(result)
    date_str = datetime.now().strftime("%d %B %Y, %H:%M UTC")
    ir = result.get("intelligence_report") or {}

    if is_withheld:
        return _build_withheld_report(result, gate or {}, dims, weak_signals, sources, date_str, ir)
    else:
        return _build_authorized_report(result, dims, weak_signals, sources, date_str, ir)


def _build_withheld_report(
    result: Dict[str, Any],
    gate: Dict[str, Any],
    dims: Dict[str, float],
    weak_signals: List[str],
    sources: List[Dict[str, Any]],
    date_str: str,
    ir: Dict[str, Any],
) -> str:
    """Build the WITHHELD briefing."""
    reasons = gate.get("reasons", [])
    proposed = _s(gate.get("proposed_decision", "UNKNOWN"))

    # Format reasons
    reason_lines = []
    for i, reason in enumerate(reasons, 1):
        reason_lines.append(f"  {i}. {reason}")
    reasons_text = "\n".join(reason_lines) if reason_lines else "  (no specific reasons recorded)"

    # Intelligence gaps
    gap_list = gate.get("intelligence_gaps", [])
    if not gap_list:
        # Pull from missing signals in the answer
        answer = _s(result.get("answer", ""))
        for line in answer.splitlines():
            if "Missing:" in line:
                sig = line.split("Missing:")[-1].strip()
                if sig:
                    gap_list.append(sig)

    # Collection requirements from PIRs
    collection_list = gate.get("required_collection", [])

    return WITHHELD_TEMPLATE.format(
        header=HEADER,
        heavy=HEAVY_LINE,
        light=LIGHT_LINE,
        confidence_word="INDETERMINATE",
        date=date_str,
        proposed=proposed,
        reason_count=len(reasons),
        reasons=reasons_text,
        dimensions=_format_dimensions(dims),
        gaps=_format_gaps(gap_list),
        collection=_format_collection(collection_list),
        indicators=_format_indicators(weak_signals, dims),
        sources=_format_sources(sources),
        source_count=len(sources),
    )


def _build_authorized_report(
    result: Dict[str, Any],
    dims: Dict[str, float],
    weak_signals: List[str],
    sources: List[Dict[str, Any]],
    date_str: str,
    ir: Dict[str, Any],
) -> str:
    """Build the normal AUTHORIZED assessment briefing."""
    risk_level = _s(result.get("risk_level", "UNKNOWN")).upper()
    confidence = _f(result.get("analytic_confidence", result.get("confidence", 0.0)))
    conf_word = confidence_word(confidence)

    # Executive summary
    exec_summary = _s(ir.get("executive_summary", ""))
    if not exec_summary:
        # Build minimal summary from risk_level
        exec_summary = f"  The system assesses the current situation as {risk_level}."
    else:
        # Indent and clean
        exec_summary = "\n".join(f"  {line}" for line in exec_summary.strip().splitlines())

    # Key indicators
    key_ind = ir.get("key_indicators") or []
    if key_ind:
        ind_lines = [f"  • {sig}" for sig in key_ind[:10]]
        key_indicators_text = "\n".join(ind_lines)
    else:
        key_indicators_text = "  No specific indicators identified."

    # Constraints
    constraints = _s(ir.get("constraint_analysis", ""))
    if constraints:
        constraints = "\n".join(f"  {line}" for line in constraints.strip().splitlines())
    else:
        constraints = "  No constraint analysis available."

    # Counterfactuals
    cfs = ir.get("counterfactuals") or []
    if cfs:
        cf_lines = [f"  • {cf}" for cf in cfs[:6]]
        cf_text = "\n".join(cf_lines)
    else:
        cf_text = "  No counterfactual triggers identified."

    # Intelligence gaps (from weak signals)
    gap_list = weak_signals if weak_signals else []
    cs = result.get("council_session", {}) or {}
    if not gap_list and isinstance(cs, dict):
        # Try missing signals from investigation metadata
        inv = cs.get("investigation_meta", {}) or {}
        gap_list = inv.get("requested_signals", [])

    return AUTHORIZED_TEMPLATE.format(
        header=HEADER,
        heavy=HEAVY_LINE,
        light=LIGHT_LINE,
        risk_level=risk_level,
        confidence_word=conf_word,
        confidence=confidence,
        date=date_str,
        executive_summary=exec_summary,
        dimensions=_format_dimensions(dims),
        key_indicators=key_indicators_text,
        constraints=constraints,
        counterfactuals=cf_text,
        gaps=_format_gaps(gap_list),
        sources=_format_sources(sources),
        source_count=len(sources),
    )


def build_report_from_pipeline_result(pipeline_result: Any) -> str:
    """
    Convenience: build report from a PipelineResult object.

    Used when the caller has the PipelineResult from unified_pipeline
    rather than the raw coordinator dict.
    """
    result_dict: Dict[str, Any] = {}

    # Map PipelineResult fields to the dict format the builder expects
    for attr in [
        "answer", "status", "outcome", "sources", "references",
        "confidence", "analytic_confidence", "epistemic_confidence",
        "risk_level", "early_warning_index", "escalation_sync",
        "prewar_detected", "warning", "intelligence_report",
        "gate_verdict", "council_session",
    ]:
        val = getattr(pipeline_result, attr, None)
        if val is not None:
            result_dict[attr] = val

    return build_user_report(result_dict)


__all__ = [
    "build_user_report",
    "build_report_from_pipeline_result",
]
