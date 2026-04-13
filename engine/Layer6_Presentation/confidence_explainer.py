"""
Confidence Explainer — Appendix A of the Intelligence Briefing
================================================================

Breaks down the confidence score into its component weights and
explains what each contributor means.  Camera rule applies.
"""

from __future__ import annotations

from typing import Any, Dict, List


# Official weight labels matching coordinator.py formula
_WEIGHTS = {
    "sensor_confidence": ("Sensor Fusion", 0.30),
    "verification_score": ("CoVe Verification", 0.20),
    "logic_score": ("Logic Consistency", 0.15),
    "meta_confidence": ("Minister Meta-Confidence", 0.20),
    "document_confidence": ("Document/RAG Confidence", 0.15),
}


def render(record: Dict[str, Any]) -> str:
    """
    Render Appendix A: Confidence Decomposition.

    Reads ``record["risk_engine"]``.
    """
    risk = record.get("risk_engine", {})
    breakdown = risk.get("confidence_breakdown", {})
    rt_penalty = risk.get("red_team_confidence_penalty", 0.0)
    final = risk.get("final_confidence", 0.0)

    lines: List[str] = []
    lines.append("## Appendix A — Confidence Decomposition")
    lines.append("")
    lines.append(f"**Final Confidence:** {final:.1%}")
    lines.append("")

    # Formula
    lines.append("### Weighted Formula")
    lines.append("")
    lines.append("```")
    lines.append("confidence = 0.30×sensor + 0.20×verification + 0.15×logic "
                 "+ 0.20×meta + 0.15×document − red_team_penalty")
    lines.append("```")
    lines.append("")

    # Component table
    lines.append("### Component Breakdown")
    lines.append("")
    lines.append("| Component | Raw Score | Weight | Contribution |")
    lines.append("|-----------|-----------|--------|-------------|")
    total_contrib = 0.0
    for key, (label, weight) in _WEIGHTS.items():
        raw = breakdown.get(key, 0.0)
        contrib = raw * weight
        total_contrib += contrib
        lines.append(f"| {label} | {raw:.3f} | {weight:.0%} | {contrib:.4f} |")

    if rt_penalty > 0:
        lines.append(f"| Red Team Penalty | −{rt_penalty:.4f} | — | −{rt_penalty:.4f} |")
        total_contrib -= rt_penalty
    lines.append(f"| **Total** | — | — | **{total_contrib:.4f}** |")
    lines.append("")

    # Interpretation
    lines.append("### Interpretation")
    lines.append("")
    if final >= 0.75:
        lines.append("Confidence is **HIGH**.  The assessment rests on strong "
                     "multi-source corroboration with verification.")
    elif final >= 0.55:
        lines.append("Confidence is **MODERATE**.  Some components are well-supported "
                     "but others have limited corroboration.")
    elif final >= 0.35:
        lines.append("Confidence is **LOW**.  Significant gaps exist in the "
                     "analytical basis.  Treat conclusions as preliminary.")
    else:
        lines.append("Confidence is **VERY LOW**.  The assessment lacks sufficient "
                     "analytical basis for reliable conclusions.")
    lines.append("")

    # Temporal trend
    trend = risk.get("temporal_trend", {})
    if trend:
        lines.append("### Temporal Trend")
        lines.append("")
        for k, v in trend.items():
            lines.append(f"  - **{k}:** {v}")
        lines.append("")

    return "\n".join(lines)
