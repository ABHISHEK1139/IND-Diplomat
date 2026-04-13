"""
Layer5_Trajectory — Trajectory Report Section Formatter
========================================================

Generates the Phase 5 trajectory outlook section for the
intelligence assessment report.

Output format:
    PHASE 5 — TRAJECTORY OUTLOOK
    Current Escalation: X% (RISK → GATE_DECISION)
    Velocity: ±X.XX (Direction)
    ...

Phase 5 ONLY.  This produces a text section that gets appended
to the main report by report_formatter.py.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("Layer5_Trajectory.trajectory_report")

_HEAVY = "=" * 66
_LIGHT = "-" * 66


def _direction_label(velocity: float) -> str:
    """Convert velocity to a human-readable direction label."""
    if velocity > 0.10:
        return "Accelerating"
    elif velocity > 0.02:
        return "Rising"
    elif velocity < -0.10:
        return "Declining rapidly"
    elif velocity < -0.02:
        return "Declining"
    else:
        return "Stable"


def _expansion_description(mode: str) -> str:
    """Human-readable expansion mode description."""
    if mode == "HIGH":
        return "HIGH — Expanded collection active, lower VOI threshold"
    elif mode == "MEDIUM":
        return "MEDIUM — Moderate expansion, additional PIRs generated"
    else:
        return "NONE — Standard collection posture"


def format_trajectory_section(
    trajectory_result,
    ndi_result=None,
    gate_decision: str = "",
) -> str:
    """
    Format the Phase 5 trajectory outlook section.

    Parameters
    ----------
    trajectory_result : TrajectoryResult
        Output from trajectory_model.compute_trajectory().
    ndi_result : NarrativeDriftResult, optional
        Output from narrative_index.compute_narrative_drift().
    gate_decision : str
        Final gate decision (APPROVED/WITHHELD/ELEVATED/etc.).

    Returns
    -------
    str
        Formatted text section for the intelligence report.
    """
    if trajectory_result is None:
        return ""

    t = trajectory_result
    sre_pct = t.current_sre * 100
    prob_up_pct = t.prob_up * 100
    prob_down_pct = t.prob_down * 100
    prob_stable_pct = t.prob_stable * 100

    vel_label = _direction_label(t.velocity)
    gate_str = f" → {gate_decision}" if gate_decision else ""

    lines = [
        "",
        _LIGHT,
        "  PHASE 5 — TRAJECTORY FORECAST  (14-day outlook)",
        _LIGHT,
        "",
        f"  Current Escalation:     {sre_pct:.1f}% ({t.current_risk}{gate_str})",
        "",
        f"  Prior (Bayesian):       {t.prior * 100:.0f}%",
        f"  Velocity:               {t.velocity:+.3f} ({vel_label})",
        f"  Structural Pressure:    {t.structural_pressure:.3f}",
        f"  Narrative Drift (NDI):  {t.narrative_drift:.3f}",
        f"  Transition Factor:      {t.transition_factor:.3f}",
        "",
        _LIGHT,
        f"  Probability of HIGH in 14 days:   {prob_up_pct:.0f}%",
        f"  Probability of LOW in 14 days:    {prob_down_pct:.0f}%",
        f"  Probability of STABLE:            {prob_stable_pct:.0f}%",
        _LIGHT,
        "",
        f"  Collection Expansion:   {_expansion_description(t.expansion_mode)}",
        f"  Pre-War Early Warning:  {'ACTIVE' if t.pre_war_warning else 'INACTIVE'}",
        f"  Acceleration Watch:     {'ACTIVE' if t.acceleration_watch else 'INACTIVE'}",
    ]

    # NDI detail if available
    if ndi_result is not None and getattr(ndi_result, "valid", False):
        lines.extend([
            "",
            "  Narrative Detail:",
            f"    Theme Velocity:       {ndi_result.theme_velocity:.3f}",
            f"    Goldstein Severity:   {ndi_result.severity_index:.3f}",
            f"    Negative Tone Shift:  {ndi_result.negative_tone_shift:.3f}",
        ])
    elif ndi_result is not None:
        lines.append("")
        lines.append("  Narrative Detail:       Insufficient GKG data (< 50 rows)")

    lines.append("")

    return "\n".join(lines)


def format_black_swan_section(black_swan_result) -> str:
    """
    Format the Black Swan monitoring section for the report.

    Parameters
    ----------
    black_swan_result : BlackSwanResult or None
        Output from black_swan_detector.detect().

    Returns
    -------
    str
        Formatted text section.  Empty string if no result available.
    """
    if black_swan_result is None:
        return ""

    bs = black_swan_result
    triggered = getattr(bs, "triggered", False)

    lines = [
        "",
        _LIGHT,
        "  PHASE 5.2 — BLACK SWAN MONITORING",
        _LIGHT,
        "",
    ]

    if not triggered:
        lines.extend([
            "  Status:                 NO DISCONTINUITY DETECTED",
            "  All three detection channels clear.",
            "",
            "  Channel 1 (Spike Severity):          CLEAR",
            "  Channel 2 (Structural Discontinuity): CLEAR",
            "  Channel 3 (Rare High-Impact Signal):  CLEAR",
        ])
    else:
        lines.extend([
            "  Status:                 *** BLACK SWAN TRIGGERED ***",
            "  Mandatory Human Review: REQUIRED",
            "",
            f"  Channels Fired:         {len(bs.channels_fired)}",
        ])
        for ch in bs.channels_fired:
            lines.append(f"    - {ch}")

        lines.append("")
        lines.append("  Trigger Reasons:")
        for reason in bs.reasons:
            lines.append(f"    ▸ {reason}")

        lines.append("")
        lines.append("  Overrides Applied:")
        lines.append(f"    Escalation Boost:     +{bs.escalation_boost:.2f}")
        lines.append(f"    Trajectory Floor:     P(HIGH) >= {bs.trajectory_floor*100:.0f}%")
        lines.append(f"    Confidence Cap:       {bs.confidence_cap:.2f}")
        lines.append(f"    Gate:                 CANNOT WITHHOLD")

    lines.append("")
    return "\n".join(lines)
