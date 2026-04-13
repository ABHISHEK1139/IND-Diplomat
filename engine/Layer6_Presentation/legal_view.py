"""
Legal View — Section 5 of the Intelligence Briefing
=====================================================

Renders the legal/treaty analysis from RAG evidence **and** the
LLM-reasoned legal constraint analysis.

Architecture:

    Part-B is NOT a legal essay generator.
    It is a **legal applicability analysis engine**.

    | Part   | Role                                 |
    | Part-A | Detects real-world behavior           |
    | Part-B | Determines legal justification space  |  ← THIS
    | Part-C | Combines both                         |

The output answers:
    "If escalation happens, how will states legally justify or restrain it?"

Camera rule: all interpretation was done by Layer-4/Layer-5
(the assessment record); this module only formats.
"""

from __future__ import annotations

from typing import Any, Dict, List


# ═══════════════════════════════════════════════════════════════════════
# STATUS → display formatting
# ═══════════════════════════════════════════════════════════════════════

_STATUS_EMOJI = {
    "prohibited": "PROHIBITED",
    "permitted": "PERMITTED",
    "conditional": "CONDITIONAL",
    "restricted": "RESTRICTED",
    "unclear": "UNCLEAR",
    "no_applicable_authority": "NO AUTHORITY",
}


def render(record: Dict[str, Any]) -> str:
    """
    Render Section 5: Legal & Treaty Framework.

    Reads ``record["legal_analysis"]`` and ``record["risk_engine"]``.
    If LLM constraint analysis is available, renders the structured
    constraint table.  Falls back to treaty excerpt listing otherwise.
    """
    legal = record.get("legal_analysis", {})
    risk = record.get("risk_engine", {})
    threat = risk.get("threat_level", "UNKNOWN")

    lines: List[str] = []

    treaties = legal.get("treaty_references", [])
    domains = legal.get("domains_covered", [])
    constraints = legal.get("legal_constraints", [])
    llm_used = legal.get("llm_reasoning_used", False)
    hallucinations = legal.get("hallucinations_blocked", 0)

    # Phase 8: skip section entirely when no legal data available.
    # Prevents rendering a misleading header with "no sources" body.
    if not treaties and not constraints:
        return ""

    lines.append("## Section 5 — Legal & Treaty Framework")
    lines.append("")

    lines.append(f"**Legal Sources:** {len(treaties)} (unique)  |  "
                 f"**Domains Covered:** {', '.join(domains) if domains else 'none'}")
    if llm_used:
        lines.append(f"**Analysis Method:** LLM-reasoned applicability analysis  |  "
                     f"**Hallucinations Blocked:** {hallucinations}")
    lines.append("")

    # ── Section A: Legal Constraint Analysis (LLM-reasoned) ──────
    if constraints:
        lines.append("### Legal Constraint Analysis")
        lines.append("")

        # Interpretation preamble
        if threat in ("HIGH", "CRITICAL"):
            lines.append(
                f"The following legal constraints represent **binding obligations** "
                f"that the assessed actor would need to violate or circumvent "
                f"to execute the {threat}-level threat posture. "
                f"Violation constitutes a secondary escalation indicator."
            )
        elif threat in ("ELEVATED", "GUARDED"):
            lines.append(
                f"The following constraints are **relevant but not determinative** "
                f"at the assessed {threat} level."
            )
        else:
            lines.append(
                f"At {threat} threat level, these represent baseline constraints."
            )
        lines.append("")

        # Constraint table
        lines.append("| Issue | Legal Status | Authority | Applies To | Confidence |")
        lines.append("|-------|-------------|-----------|------------|------------|")

        for c in constraints:
            if not isinstance(c, dict):
                continue
            issue = str(c.get("issue", "Unknown")).replace("|", "/")
            status = _STATUS_EMOJI.get(
                str(c.get("status", "unclear")).lower(), "UNCLEAR"
            )
            authority = str(c.get("authority", "—")).replace("|", "/")
            applies = ", ".join(c.get("applies_to", [])) if c.get("applies_to") else "—"
            conf = float(c.get("confidence", 0.0))
            lines.append(f"| {issue} | **{status}** | {authority} | {applies} | {conf:.0%} |")

        lines.append("")

        # Detailed reasoning for each constraint
        lines.append("### Reasoning Detail")
        lines.append("")
        for i, c in enumerate(constraints, 1):
            if not isinstance(c, dict):
                continue
            issue = c.get("issue", "Unknown")
            status = c.get("status", "unclear")
            reasoning = c.get("reasoning", "")
            condition = c.get("condition", "")

            lines.append(f"**{i}. {issue}** — {status.upper()}")
            if reasoning:
                lines.append(f"> {reasoning}")
            if condition:
                lines.append(f"> *Condition:* {condition}")
            lines.append("")

    # ── Section B: Treaty Evidence Sources ────────────────────────
    # Always show the evidence that was used, even with LLM analysis
    if treaties:
        if constraints:
            lines.append("### Supporting Treaty Evidence")
        else:
            lines.append("### Treaty Evidence")
        lines.append("")

        # Deduplicate
        _seen_legal: set = set()
        unique_treaties: List[Dict] = []
        for t in treaties:
            _key = (
                (t.get("treaty_name", "") or t.get("source", "")),
                t.get("article_number", ""),
            )
            if _key not in _seen_legal:
                _seen_legal.add(_key)
                unique_treaties.append(t)

        by_domain: Dict[str, List[Dict]] = {}
        for t in unique_treaties:
            d = t.get("domain", "general") or "general"
            by_domain.setdefault(d, []).append(t)

        for domain, refs in by_domain.items():
            lines.append(f"#### {domain.replace('_', ' ').title()}")
            lines.append("")
            for r in refs:
                treaty = r.get("treaty_name", "") or r.get("source", "")
                article = r.get("article_number", "")
                heading = r.get("heading", "")
                excerpt = r.get("excerpt", "")
                conf = r.get("confidence", 0.0)
                year = r.get("year", "")

                title_parts = [treaty]
                if article:
                    title_parts.append(f"Art. {article}")
                if year:
                    title_parts.append(f"({year})")
                title = " — ".join(title_parts)

                lines.append(f"**{title}**")
                if heading:
                    lines.append(f"*{heading}*")
                if excerpt:
                    short = excerpt[:400] + ("..." if len(excerpt) > 400 else "")
                    lines.append(f"> {short}")
                lines.append(f"Relevance: {conf:.0%}")
                lines.append("")

    # ── Section C: Analytical Integrity Notes ─────────────────────
    llm_error = legal.get("llm_reasoning_error")
    if llm_error:
        lines.append("### Analytical Notes")
        lines.append("")
        lines.append(f"*LLM reasoning encountered an error: {llm_error}. "
                     f"Constraint analysis may be incomplete.*")
        lines.append("")

    return "\n".join(lines)
