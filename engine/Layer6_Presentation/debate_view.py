"""
Debate View — Section 3 of the Intelligence Briefing
======================================================

Renders the council debate (minister positions, conflicts, consensus)
into a structured debate summary.  Camera rule applies.
"""

from __future__ import annotations

from typing import Any, Dict, List


def render(record: Dict[str, Any]) -> str:
    """
    Render Section 3: Council Deliberation.

    Reads ``record["council_debate"]``.
    """
    debate = record.get("council_debate", {})

    lines: List[str] = []
    lines.append("## Section 3 — Council Deliberation")
    lines.append("")

    # Minister positions
    positions = debate.get("minister_positions", [])
    if positions:
        lines.append("### Minister Positions")
        lines.append("")
        lines.append("| Minister | Confidence | Key Signals |")
        lines.append("|----------|------------|-------------|")
        for m in positions:
            name = m.get("minister", "?")
            conf = m.get("confidence", 0.0)
            sigs = ", ".join(m.get("predicted_signals", [])[:5]) or "—"
            lines.append(f"| {name} | {conf:.0%} | {sigs} |")
        lines.append("")

    # Debate outcome
    outcome = debate.get("debate_outcome", "")
    if outcome:
        lines.append(f"**Debate Outcome:** {outcome}")
        lines.append("")

    # Consensus points
    consensus = debate.get("consensus_points", [])
    if consensus:
        lines.append("### Points of Consensus")
        lines.append("")
        for cp in consensus:
            lines.append(f"  - {cp}")
        lines.append("")

    # Conflicts surfaced
    conflicts = debate.get("conflicts_surfaced", [])
    if not conflicts:
        conflicts = debate.get("conflicts", [])
    if conflicts:
        lines.append("### Conflicts Surfaced")
        lines.append("")
        for c in conflicts:
            if isinstance(c, dict):
                lines.append(f"  - **{c.get('type', 'conflict')}**: {c.get('description', str(c))}")
            else:
                lines.append(f"  - {c}")
        lines.append("")

    # Synthesis
    synthesis = debate.get("synthesis", "")
    if synthesis:
        lines.append("### Debate Synthesis")
        lines.append("")
        lines.append(f"> {synthesis}")
        lines.append("")

    # Debate confidence
    d_conf = debate.get("debate_confidence", 0.0)
    if d_conf:
        lines.append(f"*Debate confidence: {d_conf:.0%}*")
        lines.append("")

    if not positions and not outcome:
        lines.append("*No council debate data available for this assessment.*")
        lines.append("")

    return "\n".join(lines)
