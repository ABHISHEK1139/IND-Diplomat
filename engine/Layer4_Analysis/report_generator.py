"""
Report Generator.
Converts the CouncilSession outcome into a final intelligence assessment.
"""

from typing import Dict, Any, List, Tuple
from engine.Layer4_Analysis.council_session import CouncilSession, SessionStatus


def format_ieee_reference(evidence: Dict[str, Any], index: int) -> str:
    """
    Format evidence metadata into an IEEE-style citation.

    BOUNDARY CONTRACT NOTE: The 'excerpt' field used here is a provenance
    summary set by Layer-2/3 during signal extraction — NOT raw document text
    read by Layer-4. Layer-4 uses it only for citation formatting in the
    final output, never for reasoning.
    """
    source_name = str(evidence.get("source_name") or evidence.get("source") or "Unknown Source")
    excerpt = str(evidence.get("excerpt") or evidence.get("provenance_summary") or "").strip().replace("\n", " ")
    publication_date = str(evidence.get("publication_date") or "n.d.")
    url = str(evidence.get("url") or "")
    if excerpt:
        return f"[{index}] {source_name}, \"{excerpt}\", {publication_date}. Available: {url or 'N/A'}"
    return f"[{index}] {source_name}, {publication_date}. Available: {url or 'N/A'}"


def _coerce_evidence_row(row: Any) -> Dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    to_dict = getattr(row, "to_dict", None)
    if callable(to_dict):
        try:
            payload = to_dict()
            if isinstance(payload, dict):
                return dict(payload)
        except Exception:
            pass
    return {
        "source": str(getattr(row, "source", getattr(row, "source_name", "unknown")) or "unknown"),
        "source_name": str(getattr(row, "source", getattr(row, "source_name", "unknown")) or "unknown"),
        "date": str(getattr(row, "date", getattr(row, "publication_date", "")) or ""),
        "publication_date": str(getattr(row, "date", getattr(row, "publication_date", "")) or ""),
        "url": str(getattr(row, "url", "") or ""),
        "excerpt": str(getattr(row, "excerpt", "") or ""),
    }


def build_references(state_context: Any) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    seen = set()

    observed = list(getattr(state_context, "observed_signals", []) or [])
    signal_evidence = dict(getattr(state_context, "signal_evidence", {}) or {})
    fallback = {}
    evidence_ctx = getattr(state_context, "evidence", None)
    if evidence_ctx is not None:
        fallback = dict(getattr(evidence_ctx, "signal_provenance", {}) or {})

    for signal in observed:
        token = str(signal or "").strip().upper()
        if not token:
            continue
        rows = list(signal_evidence.get(token, []) or [])
        if not rows:
            rows = list(fallback.get(token, []) or [])
        for row in rows:
            payload = _coerce_evidence_row(row)
            key = (
                token,
                str(payload.get("source") or payload.get("source_name") or ""),
                str(payload.get("date") or payload.get("publication_date") or ""),
                str(payload.get("url") or ""),
                str(payload.get("excerpt") or payload.get("content") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                {
                    "signal": token,
                    "source": payload.get("source") or payload.get("source_name", "unknown"),
                    "date": payload.get("date") or payload.get("publication_date", ""),
                    "url": payload.get("url", ""),
                    "excerpt": payload.get("excerpt", payload.get("content", "")),
                }
            )
    return refs


def _signal_provenance(session: CouncilSession) -> Dict[str, List[Dict[str, Any]]]:
    payload = dict(getattr(session.state_context, "signal_evidence", {}) or {})
    if not payload:
        evidence = getattr(session.state_context, "evidence", None)
        payload = getattr(evidence, "signal_provenance", {}) if evidence else {}
    if not isinstance(payload, dict):
        return {}
    normalized: Dict[str, List[Dict[str, Any]]] = {}
    for signal, rows in list(payload.items()):
        key = str(signal or "").strip().upper()
        if not key:
            continue
        valid_rows: List[Dict[str, Any]] = []
        for row in list(rows or []):
            if isinstance(row, dict):
                valid_rows.append(row)
            else:
                valid_rows.append(_coerce_evidence_row(row))
        normalized[key] = valid_rows
    return normalized


def _reference_bundle(
    provenance: Dict[str, List[Dict[str, Any]]],
    signals: List[str],
) -> Tuple[Dict[str, List[int]], List[Dict[str, Any]]]:
    index_map: Dict[Tuple[str, str, str, str], int] = {}
    references: List[Dict[str, Any]] = []
    signal_refs: Dict[str, List[int]] = {}

    for signal in list(signals or []):
        token = str(signal or "").strip().upper()
        if not token:
            continue
        rows = list(provenance.get(token, []) or [])
        if not rows:
            continue
        assigned: List[int] = []
        for row in rows:
            key = (
                str(row.get("source_id", "")),
                str(row.get("url", "")),
                str(row.get("publication_date", "")),
                str(row.get("excerpt", row.get("content", ""))),
            )
            if key not in index_map:
                index_map[key] = len(references) + 1
                references.append(row)
            assigned.append(index_map[key])
        if assigned:
            signal_refs[token] = sorted(set(assigned))
    return signal_refs, references


def generate_assessment(session: CouncilSession) -> str:
    """
    Produces the final text report from the session.
    """
    if session.status == SessionStatus.INVESTIGATING:
        return _generate_investigation_notice(session)
    
    if session.status == SessionStatus.FAILED or not session.king_decision:
        return "ASSESSMENT FAILED: The Council could not reach a consensus or verify a hypothesis."

    # Successful Assessment
    best_report = session.get_best_hypothesis()
    if not best_report:
        return "ASSESSMENT FAILED: No minister reports were produced."

    best_hypothesis = None
    for item in list(session.hypotheses or []):
        if str(item.minister) == str(best_report.minister_name):
            best_hypothesis = item
            break
    if best_hypothesis is None and session.hypotheses:
        best_hypothesis = session.hypotheses[0]

    predicted = list(best_report.predicted_signals or [])
    verdict = ", ".join(predicted) if predicted else "NO_HIGH_PRIORITY_SIGNAL"
    timestamp = session.created_at.strftime("%Y-%m-%d %H:%M UTC")
    
    # Try to extract context from session meta or question
    meta = getattr(session.state_context, "meta", None) if hasattr(session, "state_context") else None
    
    if isinstance(meta, dict):
        actors = meta.get("MAIN_ACTORS") or "Unspecified"
        region = meta.get("REGION") or "Global / Unspecified"
        strategic_context = meta.get("CONTEXT") or "Standard ongoing monitoring assessment."
    else:
        actors = getattr(meta, "MAIN_ACTORS", None) or "Unspecified"
        region = getattr(meta, "REGION", None) or "Global / Unspecified"
        strategic_context = getattr(meta, "CONTEXT", None) or "Standard ongoing monitoring assessment."

    report = f"""# IND-DIPLOMAT INTELLIGENCE ASSESSMENT
**Date:** {timestamp}
**Subject:** {session.question}

**Main Actors:** {actors}
**Region:** {region}
**Strategic Context:** {strategic_context}

## Executive Summary
**Context:** Actor interaction monitored via autonomous global intelligence tracking.
**Verdict:** {verdict}
**Confidence:** {session.final_confidence:.2f} ({_confidence_label(session.final_confidence)})

## Key Judgments
- Minister: {best_report.minister_name}
- Predicted signals: {", ".join(predicted) if predicted else "None"}

## Supporting Evidence & Velocity
The following observed signals support this assessment:
"""
    matched = list(getattr(best_hypothesis, "matched_signals", []) or [])
    provenance = _signal_provenance(session)
    signal_refs, references = _reference_bundle(provenance, matched)
    
    # Attempt to grab temporal analysis if available
    temporal = getattr(session, "temporal_analysis", None)

    for signal in matched:
        token = str(signal or "").strip().upper()
        ref_ids = signal_refs.get(token, [])
        trend_str = ""
        
        # Add Time Dimension/Velocity (↑ +X% last 72 hours)
        if temporal and hasattr(temporal, "indicators") and token in temporal.indicators:
            indicator = temporal.indicators[token]
            if hasattr(indicator, "momentum") and abs(indicator.momentum) > 0.01:
                direction = "↑" if indicator.momentum > 0 else "↓"
                trend_str = f" [{direction} {(indicator.momentum * 100):+.0f}% over 72h]"

        if ref_ids:
            refs_text = ", ".join(f"[{idx}]" for idx in ref_ids)
            report += f"- {signal.replace('_', ' ').title()}{trend_str} (Refs: {refs_text})\n"
        else:
            report += f"- {signal.replace('_', ' ').title()}{trend_str}\n"

    missing = list(getattr(best_hypothesis, "missing_signals", []) or [])
    if missing:
        report += "\n## Missing Indicators (Caveats)\n"
        report += "The following expected indicators were NOT observed, reducing confidence:\n"
        for signal in missing:
            report += f"- {signal.replace('_', ' ').title()}\n"
            
    if session.identified_conflicts:
         report += "\n## Alternative Hypotheses & Conflicts\n"
         for conflict in session.identified_conflicts:
             report += f"- {conflict}\n"

    if references:
        report += "\n## References\n"
        for idx, evidence in enumerate(references, start=1):
            report += f"{format_ieee_reference(evidence, idx)}\n"

    return report

def _generate_investigation_notice(session: CouncilSession) -> str:
    needs = ", ".join(session.investigation_needs).replace("_", " ")
    return (
        f"ASSESSMENT SUSPENDED: Insufficient evidence to conclude.\n"
        f"Status: INVESTIGATION REQUESTED\n"
        f"Missing Critical Intelligence: {needs}\n"
        f"Action: Deployment of collection assets initiated."
    )

def _confidence_label(score: float) -> str:
    if score >= 0.8: return "High"
    if score >= 0.5: return "Moderate"
    return "Low"
