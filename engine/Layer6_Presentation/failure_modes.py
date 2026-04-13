"""
Failure Modes — Appendix C of the Intelligence Briefing
=========================================================

Reports on conditions under which this assessment would be wrong.
Identifies the specific failure scenarios and what indicators would
reveal them.  Camera rule applies.
"""

from __future__ import annotations

from typing import Any, Dict, List


def render(record: Dict[str, Any]) -> str:
    """
    Render Appendix C: Failure Mode Analysis.

    Reads multiple sections of the record to identify potential
    failure scenarios.
    """
    risk = record.get("risk_engine", {})
    rt = record.get("red_team", {})
    gaps = record.get("intelligence_gaps", {})
    assessment = record.get("final_assessment", {})
    beliefs = record.get("beliefs", [])
    obs = record.get("observations", {})

    threat = risk.get("threat_level", "UNKNOWN")
    confidence = risk.get("final_confidence", 0.0)

    lines: List[str] = []
    lines.append("## Appendix C — Failure Mode Analysis")
    lines.append("")
    lines.append("*Under what conditions would this assessment be wrong?*")
    lines.append("")

    modes: List[Dict[str, str]] = []

    # 1. Low confidence → inherent uncertainty
    if confidence < 0.55:
        modes.append({
            "mode": "Insufficient Analytical Basis",
            "condition": f"Confidence ({confidence:.0%}) is below the 55% threshold. "
                         f"The system itself considers this assessment unreliable.",
            "indicator": "Collection of additional sources would significantly "
                        "alter the threat level.",
            "likelihood": "HIGH",
        })

    # 2. If threat is LOW but red team found issues
    if threat in ("LOW", "GUARDED") and not rt.get("is_robust", True):
        modes.append({
            "mode": "False Negative (Under-assessment)",
            "condition": f"Threat assessed as {threat} but red team found "
                         f"the assessment not robust.",
            "indicator": "Any of the red team contradictions proving valid "
                        "would indicate a higher threat level.",
            "likelihood": "MEDIUM",
        })

    # 3. If threat is HIGH but based on few signals
    sig_count = obs.get("signal_count", 0)
    if threat in ("HIGH", "CRITICAL") and sig_count < 5:
        modes.append({
            "mode": "False Positive (Over-assessment)",
            "condition": f"Threat assessed as {threat} based on only "
                         f"{sig_count} signal(s).  Thin evidence basis.",
            "indicator": "Signals prove to be noise, routine activity, "
                        "or mis-attributed provenance.",
            "likelihood": "MEDIUM",
        })

    # 4. Stale data failure
    stale = obs.get("stale_signals", [])
    if len(stale) > 2:
        modes.append({
            "mode": "Stale Intelligence Failure",
            "condition": f"{len(stale)} stale signals included in assessment. "
                         f"Ground truth may have changed.",
            "indicator": "Fresh collection contradicts stale signal patterns.",
            "likelihood": "MEDIUM",
        })

    # 5. Missing dimension coverage
    covered_dims = {b.get("dimension") for b in beliefs if b.get("coverage", 0) > 0.3}
    all_dims = {"capability", "intent", "stability", "cost"}
    missing_dims = all_dims - covered_dims
    if missing_dims:
        modes.append({
            "mode": "Blind Dimension",
            "condition": f"Dimensions with poor coverage: "
                         f"{', '.join(sorted(missing_dims))}. "
                         f"Assessment may miss threats in unmonitored areas.",
            "indicator": f"New intelligence in {', '.join(sorted(missing_dims))} "
                        f"dimensions changes the picture.",
            "likelihood": "MEDIUM" if len(missing_dims) <= 1 else "HIGH",
        })

    # 6. Gate withheld → system itself says unreliable
    if assessment.get("gate_decision") == "WITHHELD":
        reasons = assessment.get("gate_reasons", [])
        modes.append({
            "mode": "Gate-Withheld Assessment",
            "condition": "The assessment gate itself withheld this assessment. "
                         f"Reasons: {'; '.join(reasons) if reasons else 'unspecified'}",
            "indicator": "This assessment should not be used for decision-making "
                        "without additional collection.",
            "likelihood": "HIGH",
        })

    # 7. Curiosity targets unresolved
    curiosity = gaps.get("curiosity_targets", [])
    if len(curiosity) > 3:
        modes.append({
            "mode": "Unresolved Curiosity",
            "condition": f"{len(curiosity)} curiosity-driven targets remain "
                         f"uninvestigated.  The system identified questions "
                         f"it wanted to answer but could not.",
            "indicator": "Investigation of curiosity targets would alter "
                        "confidence or threat level.",
            "likelihood": "LOW",
        })

    # Render
    if not modes:
        lines.append("**No significant failure modes identified.**")
        lines.append("")
        lines.append("*Note: This does not mean the assessment is guaranteed correct.  "
                     "It means the system's self-diagnostic checks did not find "
                     "structural weaknesses.*")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"**{len(modes)} failure mode(s) identified:**")
    lines.append("")

    for i, m in enumerate(modes, 1):
        lines.append(f"### {i}. {m['mode']} (Likelihood: {m['likelihood']})")
        lines.append("")
        lines.append(f"**Condition:** {m['condition']}")
        lines.append("")
        lines.append(f"**Would reveal itself if:** {m['indicator']}")
        lines.append("")

    return "\n".join(lines)
