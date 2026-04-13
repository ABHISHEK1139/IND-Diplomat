"""
Phase 6 — Learning Report Section
====================================

Formats the PHASE 6 — AUTONOMOUS CALIBRATION section for the
intelligence assessment report.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("Layer6_Learning.learning_report")


def format_learning_section(learning_data: Optional[Dict[str, Any]] = None) -> str:
    """Format the Phase 6 learning section for the assessment report.

    Parameters
    ----------
    learning_data : dict or None
        The ``"learning"`` key from the coordinator return dict.
        Contains forecast_summary, calibration, adjustments, etc.

    Returns
    -------
    str
        Multi-line report section, or empty string if no data.
    """
    if not learning_data:
        return ""

    lines = [
        "",
        "=" * 70,
        "  PHASE 6 — AUTONOMOUS CALIBRATION",
        "  System self-assessment of forecast accuracy and weight tuning",
        "=" * 70,
        "",
    ]

    # ── Forecast Archive Summary ──────────────────────────────────
    fs = learning_data.get("forecast_summary", {})
    lines.append("  FORECAST ARCHIVE")
    lines.append("  " + "-" * 40)
    lines.append(f"    Total Forecasts:    {fs.get('total_forecasts', 0)}")
    lines.append(f"    Resolved:           {fs.get('total_resolved', 0)}")
    lines.append(f"    Unresolved:         {fs.get('total_unresolved', 0)}")
    lines.append(f"    Newly Resolved:     {fs.get('newly_resolved', 0)}")
    lines.append("")

    # ── Calibration Score ─────────────────────────────────────────
    cal = learning_data.get("calibration", {})
    tier = cal.get("tier", "INSUFFICIENT")
    avg_brier = cal.get("avg_brier")
    brier_str = f"{avg_brier:.4f}" if avg_brier is not None else "N/A"
    n_resolved = cal.get("n_resolved", 0)
    min_req = cal.get("min_required", 20)

    lines.append("  CALIBRATION QUALITY")
    lines.append("  " + "-" * 40)
    lines.append(f"    Tier:               {tier}")
    lines.append(f"    Average Brier:      {brier_str}")
    lines.append(f"    Resolved:           {n_resolved} / {min_req} minimum")
    lines.append(f"    Auto-Adjust:        {'ELIGIBLE' if cal.get('eligible') else 'LOCKED'}")

    if tier == "INSUFFICIENT":
        remaining = max(0, min_req - n_resolved)
        lines.append(f"    Status:             Accumulating data ({remaining} more needed)")
    elif tier == "EXCELLENT":
        lines.append("    Status:             Forecast accuracy is excellent")
    elif tier == "ACCEPTABLE":
        lines.append("    Status:             Forecast accuracy within tolerance")
    elif tier == "MISCALIBRATED":
        lines.append("    Status:             Forecasts need recalibration — adjustments pending")
    lines.append("")

    # ── Per-Country Breakdown ─────────────────────────────────────
    by_country = cal.get("by_country", {})
    if by_country:
        lines.append("  PER-THEATER CALIBRATION")
        lines.append("  " + "-" * 40)
        for cc, info in sorted(by_country.items()):
            b = info.get("avg_brier")
            b_str = f"{b:.4f}" if b is not None else "N/A"
            lines.append(
                f"    {cc:6s}  Brier={b_str}  "
                f"tier={info.get('tier', '?')}  "
                f"resolved={info.get('n_resolved', 0)}"
            )
        lines.append("")

    # ── Auto-Adjustment Status ────────────────────────────────────
    adj = learning_data.get("adjustments", {})
    if adj:
        lines.append("  AUTO-THRESHOLD ADJUSTMENT")
        lines.append("  " + "-" * 40)
        lines.append(f"    Eligible:           {'YES' if adj.get('eligible') else 'NO'}")
        lines.append(f"    Reason:             {adj.get('reason', 'N/A')}")

        proposed = adj.get("proposed_deltas", {})
        if proposed:
            lines.append("    Proposed Changes:")
            for name, delta in sorted(proposed.items()):
                sign = "+" if delta > 0 else ""
                lines.append(f"      {name}: {sign}{delta:.4f}")
        lines.append("")

    # ── Confidence Recalibration ──────────────────────────────────
    mult = learning_data.get("confidence_multiplier", 1.0)
    lines.append("  CONFIDENCE RECALIBRATION")
    lines.append("  " + "-" * 40)
    lines.append(f"    Multiplier:         {mult:.4f}")
    if mult < 1.0:
        pct = round((1.0 - mult) * 100, 1)
        lines.append(f"    Effect:             -{pct}% confidence penalty")
    elif mult == 1.0:
        lines.append("    Effect:             Neutral (insufficient history)")
    lines.append("")

    # ── Drift Monitor ─────────────────────────────────────────────
    drift = learning_data.get("drift", {})
    if drift:
        lines.append("  DRIFT MONITOR")
        lines.append("  " + "-" * 40)
        for name, info in sorted(drift.items()):
            cap_flag = " [AT CAP]" if info.get("at_cap") else ""
            lines.append(
                f"    {name}: {info.get('baseline', 0):.4f} → "
                f"{info.get('current', 0):.4f}  "
                f"(drift: {info.get('drift_pct', 0):+.1f}%{cap_flag})"
            )
        lines.append("")

    return "\n".join(lines)
