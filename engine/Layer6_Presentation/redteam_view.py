"""
Red Team View — Section 4 of the Intelligence Briefing
========================================================

Renders red-team challenge results: whether the assessment survived
adversarial scrutiny, what contradictions were found, and how much
confidence was penalised.  Camera rule applies.
"""

from __future__ import annotations

from typing import Any, Dict, List


def render(record: Dict[str, Any]) -> str:
    """
    Render Section 4: Adversarial Challenge.

    Reads ``record["red_team"]``.
    """
    rt = record.get("red_team", {})

    lines: List[str] = []
    lines.append("## Section 4 — Adversarial Challenge (Red Team)")
    lines.append("")

    active = rt.get("active", False)
    if not active:
        lines.append("*Red team was not activated for this assessment.*")
        lines.append("")
        return "\n".join(lines)

    agent = rt.get("agent", "unknown")
    robust = rt.get("is_robust", True)
    penalty = rt.get("confidence_penalty", 0.0)
    challenged = rt.get("challenged_hypotheses", 0)

    # Status banner
    if robust:
        lines.append(f"**Result:** Assessment SURVIVED adversarial challenge  "
                     f"(agent: {agent})")
    else:
        lines.append(f"**Result:** Assessment found NOT ROBUST  "
                     f"(agent: {agent}, penalty: **-{penalty:.1%}**)")
    lines.append("")

    lines.append(f"**Hypotheses Challenged:** {challenged}")
    lines.append("")

    # Contradictions
    contradictions = rt.get("contradictions", [])
    if contradictions:
        lines.append("### Contradictions Identified")
        lines.append("")
        for i, c in enumerate(contradictions, 1):
            if isinstance(c, dict):
                lines.append(f"  {i}. {c.get('description', str(c))}")
            else:
                lines.append(f"  {i}. {c}")
        lines.append("")

    # Critique
    critique = rt.get("critique", "")
    if critique:
        lines.append("### Red Team Critique")
        lines.append("")
        lines.append(f"> {critique}")
        lines.append("")

    # Counter-evidence
    counter = rt.get("counter_evidence", [])
    if counter:
        lines.append("### Counter-Evidence / Challenge Queries")
        lines.append("")
        for i, ce in enumerate(counter, 1):
            lines.append(f"  {i}. {ce}")
        lines.append("")

    # Impact on confidence
    if penalty > 0:
        lines.append("### Impact on Assessment")
        lines.append("")
        lines.append(f"Red team challenge reduced overall confidence by "
                     f"**{penalty:.1%}**.  This penalty is factored into "
                     f"the final confidence score in Section 2.")
        lines.append("")

    return "\n".join(lines)
