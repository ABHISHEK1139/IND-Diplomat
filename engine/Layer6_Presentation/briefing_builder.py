"""
Briefing Builder — Master Orchestrator for Intelligence Briefings
===================================================================

Assembles the complete intelligence briefing by calling each Layer-6
view module in order.  The briefing has:

    SECTIONS (body):
        1. Empirical Evidence Base          (evidence_view)
        2. Key Judgments & Risk Assessment   (inline — from final_assessment)
        3. Council Deliberation              (debate_view)
        4. Adversarial Challenge             (redteam_view)
        5. Legal & Treaty Framework          (legal_view)
        6. Intelligence Gaps                 (gap_view)
        7. Strategic Outlook                 (inline — synthesis)

    APPENDICES:
        A. Confidence Decomposition          (confidence_explainer)
        B. Bias & Limitations Report         (bias_detector)
        C. Failure Mode Analysis             (failure_modes)

Architecture rule
-----------------
This module is a **camera**.  It NEVER computes intelligence.
Every piece of data comes from the assessment_record.json produced by
Layer-5.  If data is missing, the section says so — it does not invent.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from . import evidence_view
from . import debate_view
from . import redteam_view
from . import legal_view
from . import gap_view
from . import confidence_explainer
from . import bias_detector
from . import failure_modes

logger = logging.getLogger("Layer6_Presentation.briefing_builder")


# =====================================================================
# Section 2 — Key Judgments (inline, no separate module needed)
# =====================================================================

def _render_key_judgments(record: Dict[str, Any]) -> str:
    """Render Section 2: Key Judgments & Risk Assessment."""
    risk = record.get("risk_engine", {})
    assessment = record.get("final_assessment", {})
    judgments = assessment.get("key_judgments", [])

    lines = []
    lines.append("## Section 2 — Key Judgments & Risk Assessment")
    lines.append("")

    threat = risk.get("threat_level", "UNKNOWN")
    confidence = risk.get("final_confidence", 0.0)
    gate_decision = assessment.get("gate_decision", "WITHHELD")
    warning = risk.get("warning", "")

    # Banner
    if gate_decision == "WITHHELD":
        lines.append(f"> **ASSESSMENT WITHHELD** — The assessment gate determined "
                     f"that the intelligence basis is insufficient to support a "
                     f"reliable conclusion.")
        lines.append("")
    else:
        lines.append(f"> **Assessed Threat Level: {threat}** — "
                     f"Confidence: {confidence:.0%}")
        lines.append("")

    if warning:
        lines.append(f"> ⚠ **WARNING:** {warning}")
        lines.append("")

    # Key judgments
    if judgments:
        lines.append("### Key Judgments")
        lines.append("")
        for i, j in enumerate(judgments, 1):
            judgment = j.get("judgment", "")
            basis = j.get("basis", "")
            j_conf = j.get("confidence", 0.0)
            lines.append(f"**{i}.** {judgment}")
            if basis:
                lines.append(f"   *Basis:* {basis}")
            lines.append(f"   *Confidence:* {j_conf:.0%}")
            lines.append("")

    # SRE escalation
    sre = risk.get("sre_escalation_score", 0.0)
    if sre > 0:
        lines.append(f"**Escalation Score (SRE):** {sre:.3f}")
        sre_domains = risk.get("sre_domains", {})
        if sre_domains:
            lines.append("  " + "  |  ".join(f"{k}: {v:.3f}" for k, v in sre_domains.items()))
        lines.append("")

    return "\n".join(lines)


# =====================================================================
# Section 7 — Strategic Outlook (inline)
# =====================================================================

def _render_strategic_outlook(record: Dict[str, Any]) -> str:
    """Render Section 7: Strategic Outlook."""
    risk = record.get("risk_engine", {})
    assessment = record.get("final_assessment", {})
    gaps = record.get("intelligence_gaps", {})
    rt = record.get("red_team", {})

    lines = []
    lines.append("## Section 7 — Strategic Outlook")
    lines.append("")

    threat = risk.get("threat_level", "UNKNOWN")
    confidence = risk.get("final_confidence", 0.0)
    gate_decision = assessment.get("gate_decision", "WITHHELD")

    if gate_decision == "WITHHELD":
        lines.append("**Assessment Status:** WITHHELD.  The strategic outlook is "
                     "indeterminate until the intelligence gaps identified in "
                     "Section 6 are addressed.")
        lines.append("")
        required = gaps.get("required_collection", [])
        if required:
            lines.append("*Priority next steps:*")
            for i, task in enumerate(required[:5], 1):
                lines.append(f"  {i}. {task}")
            lines.append("")
    else:
        lines.append(f"At the assessed **{threat}** threat level with "
                     f"**{confidence:.0%}** confidence:")
        lines.append("")

        # Robust or fragile?
        if rt.get("active") and not rt.get("is_robust", True):
            lines.append("- This assessment **did not survive** red-team challenge. "
                        "Conclusions should be treated as preliminary.")
        elif rt.get("active"):
            lines.append("- This assessment **survived** adversarial challenge, "
                        "increasing confidence in the analytical basis.")

        # Gaps caveat
        missing = gaps.get("missing_signals", [])
        if missing:
            lines.append(f"- **{len(missing)} signals** remain unresolved.  "
                        f"Continued monitoring is recommended.")

        # Recommendation
        rec = assessment.get("recommendation", "")
        if rec:
            lines.append(f"- **Recommendation:** {rec}")

        lines.append("")

    # Human review flag
    if assessment.get("needs_human_review"):
        lines.append("**⚠ This assessment is flagged for mandatory human review.**")
        lines.append("")

    return "\n".join(lines)


# =====================================================================
# Public API
# =====================================================================

def build_full_briefing(record: Dict[str, Any]) -> str:
    """
    Assemble the complete intelligence briefing from an assessment record.

    Parameters
    ----------
    record : dict
        The 9-section assessment record (from assessment_record.py).

    Returns
    -------
    str
        The complete Markdown briefing.
    """
    meta = record.get("metadata", {})
    session_id = meta.get("session_id", "unknown")
    timestamp = meta.get("timestamp", datetime.now(timezone.utc).isoformat())
    country = meta.get("country", "")
    query = meta.get("query", "")
    status = meta.get("status", "")

    parts = []

    # Header
    parts.append("# INTELLIGENCE BRIEFING")
    parts.append("")
    parts.append(f"**Session:** {session_id}  |  **Date:** {timestamp}")
    if country:
        parts.append(f"**Country:** {country}")
    if query:
        parts.append(f"**Query:** {query}")
    parts.append(f"**Pipeline Status:** {status}")
    parts.append("")
    parts.append("---")
    parts.append("")

    # 7 Sections
    parts.append(evidence_view.render(record))
    parts.append("---\n")
    parts.append(_render_key_judgments(record))
    parts.append("---\n")
    parts.append(debate_view.render(record))
    parts.append("---\n")
    parts.append(redteam_view.render(record))
    parts.append("---\n")
    parts.append(legal_view.render(record))
    parts.append("---\n")
    parts.append(gap_view.render(record))
    parts.append("---\n")
    parts.append(_render_strategic_outlook(record))
    parts.append("---\n")

    # 3 Appendices
    parts.append(confidence_explainer.render(record))
    parts.append("---\n")
    parts.append(bias_detector.render(record))
    parts.append("---\n")
    parts.append(failure_modes.render(record))

    # Footer
    parts.append("---")
    parts.append("")
    parts.append(f"*Generated by IND-DIPLOMAT Layer-6 Presentation • {timestamp}*")
    parts.append("")

    return "\n".join(parts)


def build_briefing_from_file(record_path: str) -> str:
    """
    Load an assessment record from disk and produce the briefing.

    Parameters
    ----------
    record_path : str
        Path to ``assessment_record.json``.

    Returns
    -------
    str
        The complete Markdown briefing.
    """
    with open(record_path, "r", encoding="utf-8") as f:
        record = json.load(f)
    return build_full_briefing(record)


def write_briefing(
    record: Dict[str, Any],
    output_dir: Optional[str] = None,
) -> Path:
    """
    Build the briefing and write it to disk.

    Returns the path to the written file.
    """
    briefing = build_full_briefing(record)

    meta = record.get("metadata", {})
    session_id = meta.get("session_id", "unknown")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    out = Path(output_dir) if output_dir else (
        Path(__file__).resolve().parent.parent / "reports"
    )
    out.mkdir(parents=True, exist_ok=True)

    filename = f"briefing_{session_id}_{ts}.md"
    filepath = out / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(briefing)

    logger.info("Intelligence briefing written → %s", filepath)
    return filepath
