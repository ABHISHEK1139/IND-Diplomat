"""
Layer5_Judgment — Dual-Track Intelligence Report Formatter
============================================================

Transforms raw pipeline output into a **dual-track** intelligence
assessment with three analytically distinct parts:

    Part A — ESCALATION ASSESSMENT (EMPIRICAL)
             Sensor data ONLY.  No legal citations.
             Answers: "Is escalation objectively occurring?"

    Part B — LEGAL-POLITICAL ASSESSMENT (INTERPRETIVE)
             Treaty / RAG evidence ONLY.  No sensor data.
             Answers: "How will actors justify or constrain escalation?"

    Part C — STRATEGIC SYNTHESIS
             Where both tracks meet.
             Answers: "What does the combined picture mean for policy?"

Design principle:
    Law does not cause escalation — law explains how actors *justify*
    escalation.  The signal engine is a war detector (physical action);
    the legal RAG is a pre-war detector (narrative preparation).
    Merging them loses predictive power.  Keep them separate, then
    synthesize.

Usage:
    from engine.Layer5_Judgment.report_formatter import format_assessment
    report = format_assessment(pipeline_result_dict)
    print(report)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Layer5_Judgment.report_formatter")

# ── Visual constants ──────────────────────────────────────────────────
_HEAVY = "=" * 66
_LIGHT = "-" * 66
_THIN = "·" * 66
_HEADER = "  IND-DIPLOMAT  —  DUAL-TRACK INTELLIGENCE ASSESSMENT"

# ── Signal → human-readable ──────────────────────────────────────────
_SIGNAL_NAMES: Dict[str, str] = {
    # CAPABILITY
    "SIG_MIL_ESCALATION":       "Military escalation activity",
    "SIG_MIL_MOBILIZATION":     "Military mobilization (reserves / units)",
    "SIG_FORCE_POSTURE":        "Force posture changes (deployments / alerts)",
    "SIG_LOGISTICS_PREP":       "Logistics preparation (pre-positioning)",
    "SIG_LOGISTICS_SURGE":      "Logistics surge (rapid supply movement)",
    "SIG_CYBER_ACTIVITY":       "Cyber operations activity",
    "SIG_CYBER_PREPARATION":    "Cyber capability preparation",
    "SIG_WMD_RISK":             "WMD program / nuclear risk indicators",
    # INTENT
    "SIG_DIP_HOSTILITY":        "Diplomatic hostility",
    "SIG_DIP_HOSTILE_RHETORIC":  "Hostile rhetoric (official statements)",
    "SIG_ALLIANCE_SHIFT":       "Alliance realignment",
    "SIG_ALLIANCE_ACTIVATION":  "Alliance / mutual-defense activation",
    "SIG_NEGOTIATION_BREAKDOWN": "Negotiation breakdown",
    "SIG_DIPLOMACY_ACTIVE":     "Active diplomacy / de-escalation talks",
    "SIG_MARITIME_VIOLATION":   "Maritime sovereignty violation",
    "SIG_SOVEREIGNTY_BREACH":   "Sovereignty breach",
    "SIG_ILLEGAL_COERCION":     "Illegal coercion (legal assessment)",
    "SIG_COERCIVE_PRESSURE":    "Coercive pressure (grey-zone activity)",
    "SIG_COERCIVE_BARGAINING":  "Coercive bargaining posture",
    "SIG_RETALIATORY_THREAT":   "Retaliatory threat signaling",
    "SIG_DETERRENCE_SIGNALING": "Deterrence signaling",
    # STABILITY
    "SIG_INTERNAL_INSTABILITY":      "Internal instability / domestic unrest",
    "SIG_DOM_INTERNAL_INSTABILITY":  "Domestic instability (confirmed)",
    "SIG_DECEPTION_ACTIVITY":        "Deception & denial activity",
    # COST
    "SIG_ECON_PRESSURE":         "Economic pressure",
    "SIG_ECONOMIC_PRESSURE":     "Economic pressure (derived)",
    "SIG_ECO_PRESSURE_HIGH":     "High economic pressure zone",
    "SIG_ECO_SANCTIONS_ACTIVE":  "Active sanctions regime",
    "SIG_SANCTIONS_ACTIVE":      "Sanctions in effect",
}

_DIMENSION_LABELS: Dict[str, str] = {
    "CAPABILITY": "Military Capability",
    "INTENT":     "Strategic Intent",
    "STABILITY":  "Domestic Stability",
    "COST":       "Cost & Constraints",
}

_RISK_DESCRIPTIONS: Dict[str, str] = {
    "CRITICAL": (
        "Multiple escalation preconditions are simultaneously active.\n"
        "  Capability and intent indicators are both at elevated levels,\n"
        "  temporal trends show sustained momentum, and constraints are\n"
        "  insufficient to offset drivers. Immediate attention required."
    ),
    "HIGH": (
        "Significant escalation preconditions are present. Capability\n"
        "  or intent indicators are elevated, with either temporal\n"
        "  acceleration or weakening constraints. Close monitoring\n"
        "  and potential contingency activation recommended."
    ),
    "ELEVATED": (
        "Moderate escalation indicators detected. Some capability or\n"
        "  intent signals are active, but constraints partially offset\n"
        "  drivers. Active monitoring warranted — situation is fluid."
    ),
    "LOW": (
        "Escalation preconditions are not jointly satisfied. Constraints\n"
        "  exceed or balance drivers. Routine monitoring recommended."
    ),
}

# ── Legal domain → human-readable ────────────────────────────────────
_DOMAIN_LABELS: Dict[str, str] = {
    "constitution":   "Constitutional Law",
    "tax":            "Fiscal / Tax Law",
    "maritime":       "Maritime & Law of the Sea",
    "trade":          "Trade & Commerce",
    "international":  "International Law",
    "organization":   "Institutional / Organizational",
    "war":            "Law of Armed Conflict / IHL",
    "human_rights":   "Human Rights Law",
    "diplomatic":     "Diplomatic & Consular Law",
    "environment":    "Environmental Law",
    "border":         "Border & Territorial Law",
    "defense":        "Defense & Security Law",
    "investment":     "Investment & BIT Law",
}


# =====================================================================
# Internal helpers
# =====================================================================

def _sf(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _ss(v: Any, default: str = "") -> str:
    return str(v or default) if v is not None else default


def _confidence_word(val: float) -> str:
    if val >= 0.85:
        return "HIGH"
    if val >= 0.65:
        return "MODERATE"
    if val >= 0.45:
        return "LOW"
    if val >= 0.25:
        return "VERY LOW"
    return "INDETERMINATE"


def _risk_bar(score: float, width: int = 30) -> str:
    """Render a visual risk bar."""
    filled = int(score * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def _signal_human(sig: str) -> str:
    return _SIGNAL_NAMES.get(sig.upper(), sig)


# =====================================================================
# Data extraction from pipeline result dict
# =====================================================================

def _extract_sre(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract SRE domains + escalation from council_session."""
    cs = result.get("council_session") or {}
    sre = {
        "escalation_score": _sf(cs.get("sre_escalation_score", 0.0)),
        "domains": cs.get("sre_domains") or {},
    }
    # Fallback: parse from answer if not in session
    if not sre["domains"]:
        answer = _ss(result.get("answer"))
        for line in answer.splitlines():
            if "[DIMENSIONS]" in line:
                for token in line.split(","):
                    token = token.strip()
                    for dim in ["CAPABILITY", "INTENT", "STABILITY", "COST"]:
                        key = dim.lower()
                        if dim + "=" in token:
                            try:
                                sre["domains"][key] = float(token.split("=")[1])
                            except (ValueError, IndexError):
                                pass
    return sre


def _extract_signals(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract projected signals with confidence and dimension."""
    signals = []

    # From answer text [SIGNAL_PROVENANCE] section
    answer = _ss(result.get("answer"))

    # From council_session minister_reports
    cs = result.get("council_session") or {}
    ministers = cs.get("minister_reports") or {}
    for name, info in ministers.items():
        info = info or {}
        for sig in (info.get("predicted_signals") or []):
            signals.append({
                "signal": sig,
                "source": name,
                "dimension": _ss(info.get("dimension", "UNKNOWN")),
                "confidence": _sf(info.get("confidence")),
            })

    # Deduplicate keeping highest confidence
    seen: Dict[str, Dict[str, Any]] = {}
    for s in signals:
        key = s["signal"]
        if key not in seen or s["confidence"] > seen[key]["confidence"]:
            seen[key] = s
    return sorted(seen.values(), key=lambda x: -x["confidence"])


def _extract_temporal(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract temporal trend data."""
    cs = result.get("council_session") or {}
    tt = cs.get("temporal_trend") or {}
    return {
        "snapshot_count": tt.get("snapshot_count", 0),
        "escalation_patterns": tt.get("trend_override_count", 0),
        "trend_overrides": tt.get("trend_overrides", []),
        "indicators": tt.get("indicators", {}),
    }


def _extract_gate(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract gate verdict."""
    gv = result.get("gate_verdict") or {}
    if not gv:
        cs = result.get("council_session") or {}
        gv = cs.get("gate_verdict") or {}
    return gv


def _extract_weak_signals(result: Dict[str, Any]) -> List[str]:
    """Extract weak/missing signals."""
    answer = _ss(result.get("answer"))
    for line in answer.splitlines():
        if "[WEAK_SIGNALS]" in line:
            after = line.split("]", 1)[-1].strip()
            return [s.strip() for s in after.split(",") if s.strip()]
    return []


def _extract_sources(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract source list."""
    return (result.get("sources") or [])[:15]


def _extract_rag_evidence(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract RAG legal evidence from council_session."""
    cs = result.get("council_session") or {}
    return cs.get("rag_evidence") or []


# =====================================================================
# Section builders
# =====================================================================

def _section_header(result: Dict[str, Any]) -> str:
    """Build the report header block."""
    risk = _ss(result.get("risk_level", "UNKNOWN")).upper()
    conf = _sf(result.get("analytic_confidence", result.get("confidence", 0.0)))
    conf_word = _confidence_word(conf)
    ep_conf = _sf(result.get("epistemic_confidence", 0.0))
    date_str = datetime.now().strftime("%d %B %Y, %H:%M UTC")

    # SRE escalation
    sre = _extract_sre(result)
    esc_score = sre["escalation_score"]

    lines = [
        _HEADER,
        _HEAVY,
        "",
        f"  RISK LEVEL:      {risk}",
        f"  ESCALATION:      {_risk_bar(esc_score)} {esc_score:.1%}",
        f"  CONFIDENCE:      {conf_word} ({conf:.1%})",
        f"  EPISTEMIC:       {ep_conf:.1%} (evidence base quality)",
        f"  DATE:            {date_str}",
        "",
        _HEAVY,
    ]
    return "\n".join(lines)


def _section_conflict_state(result: Dict[str, Any]) -> str:
    """Conflict State — Bayesian present-state classification."""
    cs = result.get("council_session", {})
    global_data = cs.get("global_model", {})
    conflict = global_data.get("conflict_state", {})

    if not conflict or conflict.get("state") in (None, "UNKNOWN", ""):
        return ""

    state = conflict.get("state", "UNKNOWN")
    confidence = float(conflict.get("confidence", 0.0))
    posterior = conflict.get("posterior", {})
    forecast = conflict.get("forecast_14d", {})
    p_active_14d = float(conflict.get("p_active_or_higher_14d", 0.0))
    country = conflict.get("country", "")
    t_source = conflict.get("transition_source", "expert")

    state_labels = {
        "PEACE":            "PEACE",
        "CRISIS":           "CRISIS",
        "LIMITED_STRIKES":  "LIMITED STRIKES",
        "ACTIVE_CONFLICT":  "ACTIVE CONFLICT",
        "FULL_WAR":         "FULL WAR",
    }
    all_states = ["PEACE", "CRISIS", "LIMITED_STRIKES", "ACTIVE_CONFLICT", "FULL_WAR"]

    lines = [
        "",
        _HEAVY,
        "  CONFLICT STATE  (Bayesian Present-State Classification)",
        _HEAVY,
        "",
        f"  State:       {state_labels.get(state, state)}",
        f"  Confidence:  {confidence*100:.1f}%",
        f"  Country:     {country}",
        f"  Matrix:      {t_source} transition",
        "",
        "  Current State Posterior:",
    ]

    for s in all_states:
        p = float(posterior.get(s, 0.0))
        bar_len = int(p * 40)
        marker = " <<<" if s == state else ""
        lines.append(f"    {state_labels.get(s, s):18s} {p*100:5.1f}%  {'|' * bar_len}{marker}")

    # 14-day forecast
    if forecast:
        lines.append("")
        lines.append("  14-Day State Forecast:")
        for s in all_states:
            p = float(forecast.get(s, 0.0))
            bar_len = int(p * 40)
            lines.append(f"    {state_labels.get(s, s):18s} {p*100:5.1f}%  {'|' * bar_len}")
        lines.append("")
        lines.append(f"  P(ACTIVE_CONFLICT or FULL_WAR in 14d): {p_active_14d*100:.1f}%")

    # Signal observations
    observed = conflict.get("observed_groups", {})
    if observed:
        lines.append("")
        lines.append("  Observed Signal Groups:")
        for group, val in sorted(observed.items(), key=lambda x: -x[1]):
            lines.append(f"    {group:22s} {val:.3f}")

    lines.append("")
    return "\n".join(lines)


def _section_situation(result: Dict[str, Any]) -> str:
    """Part A — ESCALATION ASSESSMENT (EMPIRICAL): physical signals only."""
    risk = _ss(result.get("risk_level", "UNKNOWN")).upper()
    sre = _extract_sre(result)
    domains = sre.get("domains") or {}

    lines = [
        "",
        _HEAVY,
        "  PART A — ESCALATION ASSESSMENT  (EMPIRICAL)",
        "           Sensor data only.  No legal citations.",
        "           Answers: \"Is escalation objectively occurring?\"",
        _HEAVY,
        "",
        f"  A.1  CURRENT POSTURE",
        f"  {_LIGHT[:40]}",
        "",
    ]

    # Risk-level summary sentence
    desc = _RISK_DESCRIPTIONS.get(risk, f"  Risk level: {risk}.")
    lines.append(f"  {desc}")
    lines.append("")

    # Domain breakdown
    lines.append("  STRATEGIC DIMENSIONS:")
    lines.append("")
    for dim_key in ["capability", "intent", "stability", "cost"]:
        val = _sf(domains.get(dim_key, 0.0))
        label = _DIMENSION_LABELS.get(dim_key.upper(), dim_key.upper())
        bar = _risk_bar(val, 20)
        pct = f"{val:.0%}"
        lines.append(f"    {label:<25s} {bar}  {pct}")

    # Active signals grouped by dimension
    signals_by_dim = _group_signals_by_dimension(result)
    if signals_by_dim:
        lines.append("")
        lines.append("  ACTIVE SIGNALS:")
        for dim_key in ["CAPABILITY", "INTENT", "STABILITY", "COST"]:
            dim_sigs = signals_by_dim.get(dim_key, [])
            if dim_sigs:
                lines.append(f"    {_DIMENSION_LABELS.get(dim_key, dim_key)}:")
                for sig_name, conf in dim_sigs[:4]:
                    human = _signal_human(sig_name)
                    lines.append(f"      • {human} ({conf:.0%})")

    return "\n".join(lines)


def _group_signals_by_dimension(result: Dict[str, Any]) -> Dict[str, List[Tuple[str, float]]]:
    """Group active signals by dimension with confidence values."""
    # Parse from answer text
    answer = _ss(result.get("answer"))
    minister_dim_map = {
        "Security Minister": "CAPABILITY",
        "Economic Minister": "COST",
        "Domestic Minister": "STABILITY",
        "Diplomatic Minister": "INTENT",
    }

    cs = result.get("council_session") or {}
    ministers = cs.get("minister_reports") or {}

    grouped: Dict[str, List[Tuple[str, float]]] = {}
    for name, info in ministers.items():
        info = info or {}
        dim = _ss(info.get("dimension", "")).upper()
        if dim not in _DIMENSION_LABELS:
            dim = minister_dim_map.get(name, "UNKNOWN")
        conf = _sf(info.get("confidence", 0.0))
        for sig in (info.get("predicted_signals") or []):
            grouped.setdefault(dim, []).append((sig, conf))

    # Sort each group by confidence descending
    for dim in grouped:
        grouped[dim].sort(key=lambda x: -x[1])

    return grouped


def _section_why_risk(result: Dict[str, Any]) -> str:
    """Part A.2 — WHY RISK IS AT THIS LEVEL: SRE decomposition + temporal."""
    sre = _extract_sre(result)
    domains = sre.get("domains") or {}
    esc = sre.get("escalation_score", 0.0)
    temporal = _extract_temporal(result)

    lines = [
        "",
        f"  A.2  WHY THE RISK IS AT THIS LEVEL",
        f"  {_LIGHT[:40]}",
        "",
    ]

    # SRE formula explanation
    cap = _sf(domains.get("capability"))
    intent = _sf(domains.get("intent"))
    stab = _sf(domains.get("stability"))
    cost = _sf(domains.get("cost"))

    lines.append("  STRATEGIC RISK ENGINE (SRE) DECOMPOSITION:")
    lines.append("")
    lines.append(f"    Escalation Index = (0.35×Capability + 0.30×Intent")
    lines.append(f"                     + 0.20×Stability) × (1 - 0.5×Cost) + Trend Bonus")
    lines.append("")

    # Calculate base score
    base_raw = (0.35 * cap + 0.30 * intent + 0.20 * stab)
    base = base_raw * (1.0 - 0.5 * cost)
    trend_bonus = max(0.0, esc - base)

    lines.append(f"    Raw Force:         {base_raw:.3f}  (Cap, Int, Stab)")
    lines.append(f"    Cost Constraint:   {1.0 - 0.5 * cost:.3f}  (Multiplier)")
    lines.append(f"    {'─'*40}")
    lines.append(f"    Base score:                    {base:.3f}")
    if trend_bonus > 0.001:
        lines.append(f"    Trend bonus:                  +{trend_bonus:.3f}")
    lines.append(f"    ESCALATION INDEX:              {esc:.3f}")

    # Drivers vs constraints
    lines.append("")
    driver_val = max(cap, intent)
    constraint_val = cost

    if driver_val > 0.5 and constraint_val < 0.4:
        lines.append("  DRIVER/CONSTRAINT BALANCE:")
        lines.append(f"    Drivers (capability + intent) are DOMINANT.")
        lines.append(f"    Constraints (cost/sanctions) are INSUFFICIENT to offset.")
    elif constraint_val > driver_val:
        lines.append("  DRIVER/CONSTRAINT BALANCE:")
        lines.append(f"    Constraints EXCEED drivers — restraining escalation.")
    else:
        lines.append("  DRIVER/CONSTRAINT BALANCE:")
        lines.append(f"    Drivers and constraints are roughly balanced.")

    # Temporal trends
    trend_overrides = temporal.get("trend_overrides") or []
    snap_count = temporal.get("snapshot_count", 0)
    esc_patterns = temporal.get("escalation_patterns", 0)

    if trend_overrides or esc_patterns > 0 or snap_count > 0:
        lines.append("")
        lines.append("  TEMPORAL TREND ANALYSIS:")
        if snap_count:
            lines.append(f"    History depth: {snap_count} observation snapshots")
        if esc_patterns > 0:
            lines.append(f"    Escalation patterns detected: {esc_patterns}")
            for sig in trend_overrides[:5]:
                lines.append(f"      ↑ {_signal_human(sig)} — sustained momentum")
        if trend_bonus > 0.001:
            lines.append(f"    Trend bonus applied: +{trend_bonus:.3f} to escalation index")

    return "\n".join(lines)


# ── Phase 5 — TRAJECTORY FORECAST ────────────────────────────────────

def _section_trajectory(result: Dict[str, Any]) -> str:
    """Phase 5 — TRAJECTORY FORECAST: 14-day escalation outlook."""
    cs = result.get("council_session", {})
    trajectory = cs.get("trajectory")
    ndi = cs.get("ndi")

    if trajectory is None:
        return ""

    try:
        from engine.Layer5_Trajectory.trajectory_report import format_trajectory_section
        from engine.Layer5_Trajectory.trajectory_model import TrajectoryResult
        from engine.Layer5_Trajectory.narrative_index import NarrativeDriftResult

        # Reconstruct dataclass from dict if needed
        if isinstance(trajectory, dict):
            t = TrajectoryResult(**{
                k: v for k, v in trajectory.items()
                if k in TrajectoryResult.__dataclass_fields__
            })
        else:
            t = trajectory

        n = None
        if isinstance(ndi, dict):
            n = NarrativeDriftResult(**{
                k: v for k, v in ndi.items()
                if k in NarrativeDriftResult.__dataclass_fields__
            })
        elif ndi is not None:
            n = ndi

        gate_decision = cs.get("status", result.get("risk_level", ""))
        return format_trajectory_section(t, n, gate_decision)
    except Exception as exc:
        logger.warning("[REPORT] Trajectory section failed: %s", exc)
        return ""


def _section_black_swan(result: Dict[str, Any]) -> str:
    """Phase 5.2 — BLACK SWAN MONITORING section."""
    cs = result.get("council_session", {})
    bs = cs.get("black_swan")

    if bs is None:
        return ""

    try:
        from engine.Layer5_Trajectory.trajectory_report import format_black_swan_section
        from engine.Layer5_Trajectory.black_swan_detector import BlackSwanResult

        if isinstance(bs, dict):
            obj = BlackSwanResult(**{
                k: v for k, v in bs.items()
                if k in BlackSwanResult.__dataclass_fields__
            })
        else:
            obj = bs

        return format_black_swan_section(obj)
    except Exception as exc:
        logger.warning("[REPORT] Black Swan section failed: %s", exc)
        return ""


# ── Phase 6 — AUTONOMOUS CALIBRATION ─────────────────────────────────

def _section_learning(result: Dict[str, Any]) -> str:
    """Phase 6 — AUTONOMOUS CALIBRATION section."""
    cs = result.get("council_session", {})
    learning = cs.get("learning")

    if not learning:
        return ""

    try:
        from engine.Layer6_Learning.learning_report import format_learning_section
        return format_learning_section(learning)
    except Exception as exc:
        logger.warning("[REPORT] Learning section failed: %s", exc)
        return ""


# ── Phase 7 — GLOBAL STRATEGIC SYNCHRONIZATION ──────────────────────

def _section_global(result: Dict[str, Any]) -> str:
    """Phase 7 — GLOBAL STRATEGIC SYNCHRONIZATION section."""
    cs = result.get("council_session", {})
    global_data = cs.get("global_model")

    if not global_data:
        return ""

    try:
        from engine.Layer7_GlobalModel.global_report import format_global_section
        return format_global_section(global_data)
    except Exception as exc:
        logger.warning("[REPORT] Global section failed: %s", exc)
        return ""


# ── Part B — LEGAL-POLITICAL ASSESSMENT ──────────────────────────────

def _part_b_legal(result: Dict[str, Any]) -> str:
    """Part B — LEGAL-POLITICAL ASSESSMENT (INTERPRETIVE).

    Treaty / RAG evidence ONLY.  No sensor data.
    Answers: "How will actors justify or constrain escalation?"
    """
    rag = _extract_rag_evidence(result)

    lines = [
        "",
        _HEAVY,
        "  PART B — LEGAL-POLITICAL ASSESSMENT  (INTERPRETIVE)",
        "           Treaty & legal evidence only.  No sensor data.",
        "           Answers: \"How will actors justify or constrain escalation?\"",
        _HEAVY,
        "",
    ]

    if not rag:
        lines.append("  No legal evidence retrieved for the current signal set.")
        lines.append("  RAG retrieval returned zero documents above relevance threshold.")
        lines.append("")
        return "\n".join(lines)

    # ── B.1  Treaty relevance by domain ──
    lines.append("  B.1  TREATY RELEVANCE BY DOMAIN")
    lines.append(f"  {_LIGHT[:40]}")
    lines.append("")

    # Group evidence by domain
    by_domain: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for rec in rag:
        dom = rec.get("domain", "unknown") or "unknown"
        by_domain[dom].append(rec)

    # Sort domains by count descending
    for dom in sorted(by_domain, key=lambda d: -len(by_domain[d])):
        recs = by_domain[dom]
        label = _DOMAIN_LABELS.get(dom, dom.replace("_", " ").title())
        lines.append(f"    {label}  ({len(recs)} article(s))")

        # Show top 3 articles per domain
        for rec in sorted(recs, key=lambda r: -r.get("relevance", 0))[:3]:
            treaty = rec.get("treaty_name") or rec.get("root", "?")
            art_num = rec.get("article_number", "")
            rel = rec.get("relevance", 0.0)
            heading = rec.get("heading", "")

            art_label = f"Art. {art_num}" if art_num else ""
            title_parts = [p for p in [treaty, art_label, heading] if p]
            title_str = " — ".join(title_parts)

            lines.append(f"      • {title_str}  (relevance {rel:.0%})")

            # Show first 120 chars of excerpt
            excerpt = rec.get("excerpt", "")[:120].strip()
            if excerpt:
                lines.append(f"        \"{excerpt}...\"")

        lines.append("")

    # ── B.2  Justification pathways ──
    lines.append("  B.2  JUSTIFICATION & CONSTRAINT PATHWAYS")
    lines.append(f"  {_LIGHT[:40]}")
    lines.append("")

    # Self-defense / sovereignty / IHL pathway detection
    justification_keywords = {
        "self-defense": ["self-defence", "self-defense", "article 51", "inherent right"],
        "collective defense": ["collective", "mutual defense", "alliance", "nato", "article 5"],
        "sovereignty": ["territorial integrity", "sovereignty", "non-intervention"],
        "humanitarian": ["humanitarian", "r2p", "responsibility to protect", "civilian"],
        "sanctions": ["sanction", "embargo", "restrictive measures", "economic coercion"],
        "maritime": ["exclusive economic zone", "eez", "unclos", "continental shelf", "freedom of navigation"],
    }

    pathways_found: Dict[str, List[str]] = {}
    for rec in rag:
        text = (rec.get("excerpt", "") + " " + rec.get("heading", "")).lower()
        for pathway, keywords in justification_keywords.items():
            if any(kw in text for kw in keywords):
                treaty = rec.get("treaty_name") or rec.get("root", "?")
                art_num = rec.get("article_number", "")
                ref = f"{treaty} Art.{art_num}" if art_num else treaty
                pathways_found.setdefault(pathway, []).append(ref)

    if pathways_found:
        for pathway, refs in pathways_found.items():
            unique_refs = list(dict.fromkeys(refs))[:3]  # dedup, top 3
            lines.append(f"    {pathway.upper()}:")
            for ref in unique_refs:
                lines.append(f"      → {ref}")
        lines.append("")
    else:
        lines.append("    No specific justification pathways detected in retrieved articles.")
        lines.append("")

    # ── B.3  Document confidence ──
    doc_conf = _sf((result.get("council_session") or {}).get("document_confidence", 0.0))
    avg_rel = sum(r.get("relevance", 0) for r in rag) / max(1, len(rag))

    lines.append("  B.3  LEGAL EVIDENCE QUALITY")
    lines.append(f"  {_LIGHT[:40]}")
    lines.append("")
    lines.append(f"    Total articles retrieved:    {len(rag)}")
    lines.append(f"    Domains covered:             {len(by_domain)}")
    lines.append(f"    Average relevance:           {avg_rel:.1%}")
    lines.append(f"    Document confidence:          {doc_conf:.1%}")
    lines.append("")

    return "\n".join(lines)


# ── Part C — STRATEGIC SYNTHESIS ─────────────────────────────────────

def _part_c_synthesis(result: Dict[str, Any]) -> str:
    """Part C — STRATEGIC SYNTHESIS: where empirical and legal meet."""
    sre = _extract_sre(result)
    esc = sre.get("escalation_score", 0.0)
    domains = sre.get("domains") or {}
    rag = _extract_rag_evidence(result)
    risk = _ss(result.get("risk_level", "UNKNOWN")).upper()
    doc_conf = _sf((result.get("council_session") or {}).get("document_confidence", 0.0))

    lines = [
        "",
        _HEAVY,
        "  PART C — STRATEGIC SYNTHESIS",
        "           Where empirical and legal-political evidence meet.",
        "           Answers: \"What does the combined picture mean for policy?\"",
        _HEAVY,
        "",
    ]

    # ── Physical signal summary ──
    cap = _sf(domains.get("capability"))
    intent = _sf(domains.get("intent"))
    physical_level = "HIGH" if max(cap, intent) > 0.6 else "MODERATE" if max(cap, intent) > 0.35 else "LOW"

    lines.append("  PHYSICAL ESCALATION:")
    lines.append(f"    Level: {physical_level} (cap={cap:.0%}, intent={intent:.0%}, esc={esc:.0%})")
    lines.append("")

    # ── Legal narrative summary ──
    justification_domains = {"war", "defense", "maritime", "border"}
    constraint_domains = {"human_rights", "trade", "diplomatic", "investment"}
    just_count = 0
    const_count = 0

    if rag:
        # Count justification-type vs constraint-type articles
        just_count = sum(1 for r in rag if r.get("domain", "") in justification_domains)
        const_count = sum(1 for r in rag if r.get("domain", "") in constraint_domains)

        if just_count > const_count:
            narrative = "JUSTIFICATION-DOMINANT"
            narrative_desc = "Legal evidence skews toward enabling frameworks (use-of-force, defense, sovereignty)."
        elif const_count > just_count:
            narrative = "CONSTRAINT-DOMINANT"
            narrative_desc = "Legal evidence skews toward restraining frameworks (human rights, trade, diplomatic immunity)."
        else:
            narrative = "BALANCED"
            narrative_desc = "Legal evidence is evenly split between enabling and restraining frameworks."

        lines.append("  LEGAL NARRATIVE:")
        lines.append(f"    Pattern: {narrative} ({just_count} enabling / {const_count} constraining / {len(rag)-just_count-const_count} other)")
        lines.append(f"    {narrative_desc}")
        lines.append("")
    else:
        lines.append("  LEGAL NARRATIVE:")
        lines.append("    No legal evidence available for synthesis.")
        lines.append("")

    # ── Combined assessment ──
    lines.append("  COMBINED ASSESSMENT:")
    lines.append("")

    # Generate synthesis sentence based on physical + legal
    if esc > 0.6 and rag and doc_conf > 0.3:
        if just_count > const_count:
            lines.append("    ⚠  HIGH physical escalation + JUSTIFICATION-dominant legal narrative")
            lines.append("       = Elevated probability of formal conflict initiation.")
            lines.append("       Actors are both escalating AND building legal cover.")
        else:
            lines.append("    ⚠  HIGH physical escalation + CONSTRAINT-aligned legal evidence")
            lines.append("       = Escalation is occurring DESPITE legal constraints.")
            lines.append("       Watch for constraint erosion or selective legal reinterpretation.")
    elif esc > 0.6 and (not rag or doc_conf < 0.2):
        lines.append("    ⚠  HIGH physical escalation but WEAK legal evidence base.")
        lines.append("       Cannot assess narrative preparation.  Collection priority: LEGAL/OSINT.")
    elif esc <= 0.4 and rag and doc_conf > 0.3:
        if just_count > const_count:
            lines.append("    ▲  LOW physical escalation but JUSTIFICATION narratives emerging.")
            lines.append("       Pre-war narrative preparation may precede physical escalation.")
            lines.append("       This is a LEADING INDICATOR — monitor for capability surge.")
        else:
            lines.append("    ✓  LOW physical escalation + CONSTRAINT-aligned legal evidence.")
            lines.append("       De-escalation pathway is supported by both tracks.")
    else:
        lines.append(f"    Escalation index: {esc:.0%}  |  Document confidence: {doc_conf:.0%}")
        lines.append(f"    Legal articles: {len(rag)}  |  Risk level: {risk}")
        lines.append("    Insufficient polarity for definitive synthesis.")

    # ── Pre-war indicator ──
    prewar = result.get("prewar_detected", False)
    ew_index = _sf(result.get("early_warning_index", 0.0))
    if prewar:
        lines.append("")
        lines.append("    *** PRE-WAR INDICATOR ACTIVE ***")
        lines.append(f"    Early-warning index: {ew_index:.0%}")
        if rag and just_count > const_count:
            lines.append("    CORROBORATED: Legal justification narrative aligns with physical indicators.")

    lines.append("")
    return "\n".join(lines)


def _section_watch(result: Dict[str, Any]) -> str:
    """WHAT TO WATCH NEXT — Indicators and collection needs."""
    weak = _extract_weak_signals(result)
    gate = _extract_gate(result)
    gaps = gate.get("intelligence_gaps") or []
    collection = gate.get("collection_tasks") or []

    lines = [
        "",
        f"{_LIGHT}",
        "  WHAT TO WATCH NEXT",
        f"{_LIGHT}",
        "",
    ]

    # Early-warning indicators
    lines.append("  INDICATORS THAT WOULD CHANGE THIS ASSESSMENT:")
    lines.append("")

    # De-escalation indicators
    de_escalation = [
        "Resumption of direct diplomatic negotiations",
        "Withdrawal of forward-deployed military assets",
        "Sanctions relief or economic engagement signals",
        "Third-party mediation acceptance",
    ]

    # Escalation indicators
    escalation = [
        "Confirmed military mobilization beyond current posture",
        "Diplomatic channel closure (embassy recall / expulsion)",
        "Cyber attack on critical infrastructure (confirmed)",
        "WMD program acceleration (enrichment / testing)",
        "Alliance treaty invocation (Article-5 style commitment)",
    ]

    lines.append("    Would INCREASE risk:")
    for ind in escalation[:5]:
        lines.append(f"      ▲ {ind}")

    lines.append("")
    lines.append("    Would DECREASE risk:")
    for ind in de_escalation[:4]:
        lines.append(f"      ▼ {ind}")

    # Intelligence gaps
    if weak or gaps:
        lines.append("")
        lines.append("  INTELLIGENCE GAPS (signals with insufficient data):")
        lines.append("")
        seen = set()
        for sig in (weak + gaps):
            sig_upper = sig.upper().strip()
            if sig_upper not in seen:
                seen.add(sig_upper)
                lines.append(f"    ? {_signal_human(sig_upper)}")

    # Collection requirements from gate
    if collection:
        lines.append("")
        lines.append("  RECOMMENDED COLLECTION PRIORITIES:")
        lines.append("")
        for i, task in enumerate(collection[:8], 1):
            sig = task.get("signal", "?")
            modality = task.get("modality", "OSINT")
            priority = task.get("priority", "STANDARD")
            lines.append(f"    {i}. [{priority}] {_signal_human(sig)}")
            lines.append(f"       Collection: {modality}")

    return "\n".join(lines)


def _section_sources(result: Dict[str, Any]) -> str:
    """Source attribution — split into Sensor and Legal sources."""
    sources = _extract_sources(result)
    rag = _extract_rag_evidence(result)

    # Separate sensor sources from RAG sources
    sensor_sources = [s for s in sources if not _ss(s.get("source", "")).startswith("RAG/")]
    legal_sources = [s for s in sources if _ss(s.get("source", "")).startswith("RAG/")]

    lines = [
        "",
        f"{_LIGHT}",
        "  SOURCES & ATTRIBUTION",
        f"{_LIGHT}",
        "",
    ]

    # Sensor sources
    lines.append("  SENSOR / OSINT SOURCES:")
    if not sensor_sources:
        lines.append("    GDELT event database, MoltBot OSINT sweep,")
        lines.append("    economic indicators.")
    else:
        seen: set = set()
        for src in sensor_sources:
            name = _ss(src.get("source", src.get("id", "?")))
            url = _ss(src.get("url", ""))
            date = _ss(src.get("date", ""))
            key = (name, url)
            if key in seen:
                continue
            seen.add(key)
            line = f"    • {name}"
            if date:
                line += f"  ({date})"
            if url:
                line += f"\n      {url}"
            lines.append(line)

    lines.append("")

    # Legal sources (from RAG evidence)
    lines.append("  LEGAL / TREATY SOURCES:")
    if not rag:
        lines.append("    No legal sources retrieved.")
    else:
        seen_treaties: set = set()
        for rec in sorted(rag, key=lambda r: -r.get("relevance", 0)):
            treaty = rec.get("treaty_name") or rec.get("root", "?")
            art_num = rec.get("article_number", "")
            domain = rec.get("domain", "")
            label = f"{treaty}"
            if art_num:
                label += f" Art. {art_num}"
            if label in seen_treaties:
                continue
            seen_treaties.add(label)
            dom_label = _DOMAIN_LABELS.get(domain, "") if domain else ""
            if dom_label:
                lines.append(f"    • {label}  [{dom_label}]")
            else:
                lines.append(f"    • {label}")
            if len(seen_treaties) >= 20:
                lines.append(f"    ... and {len(rag) - 20} more")
                break

    return "\n".join(lines)


def _section_methodology(result: Dict[str, Any]) -> str:
    """Methodology note — helps evaluators understand the pipeline."""
    gate = _extract_gate(result)
    risk = _ss(result.get("risk_level", "UNKNOWN")).upper()
    approved = gate.get("approved", False)

    lines = [
        "",
        f"{_LIGHT}",
        "  METHODOLOGY & CONFIDENCE",
        f"{_LIGHT}",
        "",
        "  This assessment was produced by the IND-Diplomat automated",
        "  intelligence pipeline using the following process:",
        "",
        "    1. COLLECTION    GDELT event database + MoltBot OSINT sweep",
        "                     → raw observations (events, articles)",
        "    2. EXTRACTION    Signal extraction → belief accumulation",
        "                     → temporal memory snapshot",
        "    3. PROJECTION    Fuzzy belief membership → dimensional signals",
        "                     → confidence-weighted projection",
        "    4. ANALYSIS      4-minister council deliberation →",
        "                     Strategic Risk Engine (SRE) fusion",
        "    5. RAG BRIDGE    Legal corpus retrieval (ChromaDB) →",
        "                     treaty-level evidence injection",
        "    6. JUDGMENT      Assessment gate: deterministic rules",
        f"                     → {'APPROVED' if approved else 'WITHHELD'}",
        "    7. PRESENTATION  Dual-track intelligence report",
        "                     Part A (empirical) / Part B (legal) / Part C (synthesis)",
        "",
    ]

    conf = _sf(result.get("analytic_confidence", 0.0))
    ep = _sf(result.get("epistemic_confidence", 0.0))

    lines.append(f"  Analytic Confidence:   {_confidence_word(conf)} ({conf:.1%})")
    lines.append(f"  Epistemic Confidence:  {ep:.1%}")
    lines.append(f"  Assessment Status:     {'APPROVED' if approved else 'WITHHELD'}")
    lines.append(f"  Risk Level:            {risk}")

    if not approved and gate.get("reasons"):
        lines.append("")
        lines.append("  Gate withheld because:")
        for i, reason in enumerate(gate["reasons"][:5], 1):
            lines.append(f"    {i}. {str(reason)[:100]}")

    lines.append("")
    lines.append(_HEAVY)

    return "\n".join(lines)


# =====================================================================
# Public API
# =====================================================================

def format_assessment(result: Dict[str, Any]) -> str:
    """
    Format a full intelligence assessment report from pipeline output.

    Parameters
    ----------
    result : dict
        Raw dict from ``CouncilCoordinator.process_query()`` or
        equiv. fields from ``PipelineResult.__dict__``.

    Returns
    -------
    str
        Multi-section intelligence report.
    """
    sections = [
        _section_header(result),
        _section_conflict_state(result), # Conflict State — Present-state classification
        _section_situation(result),      # Part A.1 — Empirical posture
        _section_why_risk(result),       # Part A.2 — SRE + temporal
        _section_trajectory(result),     # Phase 5  — Trajectory forecast
        _section_black_swan(result),     # Phase 5.2 — Black Swan monitoring
        _section_learning(result),       # Phase 6   — Autonomous calibration
        _section_global(result),         # Phase 7   — Global strategic sync
        _part_b_legal(result),           # Part B   — Legal-political
        _part_c_synthesis(result),       # Part C   — Strategic synthesis
        _section_watch(result),
        _section_sources(result),
        _section_methodology(result),
    ]
    report = "\n".join(sections)
    logger.info(
        "[REPORT] Formatted %d-character assessment report (risk=%s)",
        len(report), _ss(result.get("risk_level", "?")),
    )
    return report


def format_from_pipeline(pipeline_result: Any) -> str:
    """
    Format report from a PipelineResult object.

    Convenience wrapper that converts PipelineResult to dict
    then calls ``format_assessment()``.
    """
    if isinstance(pipeline_result, dict):
        return format_assessment(pipeline_result)

    result_dict: Dict[str, Any] = {}
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

    return format_assessment(result_dict)


__all__ = [
    "format_assessment",
    "format_from_pipeline",
]
