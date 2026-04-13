"""
Gap View — Section 6 of the Intelligence Briefing
===================================================

Renders intelligence gaps: what the system knows it does NOT know.
PIRs, missing signals, curiosity targets, and required collection.
Camera rule applies.
"""

from __future__ import annotations

from typing import Any, Dict, List


def render(record: Dict[str, Any]) -> str:
    """
    Render Section 6: Intelligence Gaps & Collection Requirements.

    Reads ``record["intelligence_gaps"]`` and ``record["final_assessment"]``.
    """
    gaps = record.get("intelligence_gaps", {})
    assessment = record.get("final_assessment", {})

    lines: List[str] = []
    lines.append("## Section 6 — Intelligence Gaps & Collection Requirements")
    lines.append("")

    missing = gaps.get("missing_signals", [])
    intel_gaps = gaps.get("intelligence_gaps", [])
    required = gaps.get("required_collection", [])
    curiosity = gaps.get("curiosity_targets", [])
    pir_count = gaps.get("pir_count", 0)
    critical = gaps.get("critical_pirs", 0)

    # Summary line
    gap_count = len(missing) + len(intel_gaps)
    lines.append(f"**Total Gaps Identified:** {gap_count}  |  "
                 f"**PIRs:** {pir_count} (critical: {critical})  |  "
                 f"**Collection Tasks:** {len(required)}")
    lines.append("")

    # Gate-identified gaps
    if intel_gaps:
        lines.append("### Assessment Gate — Intelligence Gaps")
        lines.append("")
        lines.append("*The following gaps caused or contributed to the gate's verdict:*")
        lines.append("")
        for g in intel_gaps:
            lines.append(f"  - {g}")
        lines.append("")

    # Missing signals from hypothesis coverage
    if missing:
        lines.append("### Missing Signals (Hypothesis Coverage Gaps)")
        lines.append("")
        for s in missing[:20]:
            lines.append(f"  - {s}")
        if len(missing) > 20:
            lines.append(f"  - *... and {len(missing) - 20} more*")
        lines.append("")

    # Required collection
    if required:
        lines.append("### Required Collection")
        lines.append("")
        lines.append("*To unlock a stronger assessment, the following collection is needed:*")
        lines.append("")
        for i, task in enumerate(required, 1):
            lines.append(f"  {i}. {task}")
        lines.append("")

    # Curiosity-driven targets (VOI)
    if curiosity:
        lines.append("### Curiosity-Driven Targets (Value of Information)")
        lines.append("")
        for t in curiosity[:10]:
            if isinstance(t, dict):
                desc = t.get("signal", t.get("description", t.get("target", str(t))))
                voi = t.get("voi", t.get("value", ""))
                reason = t.get("reason", "")
                dim = t.get("primary_dimension", "")
                parts = [desc]
                if dim:
                    parts.append(f"dimension: {dim}")
                label = " — ".join(parts)
                if voi:
                    lines.append(f"  - {label} (VOI: {voi:.3f})" if isinstance(voi, (int, float)) else f"  - {label} (VOI: {voi})")
                else:
                    lines.append(f"  - {label}")
                if reason:
                    lines.append(f"    *{reason}*")
            else:
                lines.append(f"  - {t}")
        lines.append("")

    if not gap_count and not required and not curiosity:
        lines.append("*No significant intelligence gaps identified.*")
        lines.append("")

    return "\n".join(lines)
