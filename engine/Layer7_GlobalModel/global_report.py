"""
Phase 7 — Global Report Section
==================================

Formats the PHASE 7 — GLOBAL STRATEGIC SYNCHRONIZATION section
for the intelligence assessment report.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("Layer7_GlobalModel.global_report")


def format_global_section(global_data: Optional[Dict[str, Any]] = None) -> str:
    """Format the Phase 7 global section for the assessment report.

    Parameters
    ----------
    global_data : dict or None
        The ``"global_model"`` key from the coordinator return dict.
        Contains theater_summary, contagion, risk_summary, etc.

    Returns
    -------
    str
        Multi-line report section, or empty string if no data.
    """
    if not global_data:
        return ""

    lines = [
        "",
        "=" * 70,
        "  PHASE 7 — GLOBAL STRATEGIC SYNCHRONIZATION",
        "  Multi-theater escalation contagion and systemic risk",
        "=" * 70,
        "",
    ]

    # ── Active Theaters ───────────────────────────────────────────
    risk = global_data.get("risk_summary", {})
    theaters = risk.get("theaters", [])

    lines.append("  ACTIVE THEATERS")
    lines.append("  " + "-" * 55)
    lines.append(
        f"  {'THEATER':8s}  {'SRE':>7s}  {'P(HIGH)':>8s}  "
        f"{'CONTAGION':>9s}  {'MODE':12s}"
    )
    lines.append("  " + "-" * 55)

    if theaters:
        for t in theaters:
            lines.append(
                f"  {t['country']:8s}  {t['sre']:7.3f}  "
                f"{t['prob_high']*100:7.1f}%  "
                f"{t.get('contagion_received', 0):9.3f}  "
                f"{t.get('expansion_mode', 'IDLE'):12s}"
            )
    else:
        lines.append("  No active theaters registered.")
    lines.append("")

    # ── Risk Summary ──────────────────────────────────────────────
    lines.append("  SYSTEMIC RISK ASSESSMENT")
    lines.append("  " + "-" * 55)
    lines.append(f"    Active Theaters:    {risk.get('active_count', 0)} / {risk.get('total_theaters', 0)}")
    lines.append(f"    Total SRE:          {risk.get('total_sre', 0):.3f}")
    lines.append(f"    Average SRE:        {risk.get('avg_sre', 0):.3f}")
    lines.append(f"    Highest Risk:       {risk.get('max_theater', 'N/A')} (SRE={risk.get('max_sre', 0):.3f})")

    systemic = risk.get("systemic_risk", False)
    if systemic:
        lines.append("    *** SYSTEMIC CASCADE DETECTED — GLOBAL ALERT ***")
    else:
        lines.append("    Systemic Cascade:   No (threshold: 4.0)")
    lines.append("")

    # ── Contagion Report ──────────────────────────────────────────
    contagion = global_data.get("contagion", {})
    if contagion:
        lines.append("  CONTAGION PROPAGATION")
        lines.append("  " + "-" * 55)
        for source, targets in sorted(contagion.items()):
            target_str = ", ".join(
                f"{t}+{v:.3f}" for t, v in sorted(targets.items(), key=lambda x: -x[1])
            )
            lines.append(f"    {source} → {target_str}")
        lines.append("")

    # ── Cross-Theater Forecast Adjustment ─────────────────────────
    adj = global_data.get("adjusted_forecast", {})
    if adj:
        base = adj.get("base_prob", 0)
        spillover = adj.get("spillover", 0)
        adjusted = adj.get("adjusted_prob", 0)
        contributors = adj.get("contributors", [])

        lines.append("  CROSS-THEATER FORECAST ADJUSTMENT")
        lines.append("  " + "-" * 55)
        lines.append(f"    Base P(HIGH 14d):   {base*100:.1f}%")
        lines.append(f"    Spillover:          +{spillover*100:.1f}%")
        lines.append(f"    Adjusted P(HIGH):   {adjusted*100:.1f}%")

        if contributors:
            lines.append("    Contributors:")
            for c in contributors:
                lines.append(
                    f"      {c['source']}: P(HIGH)={c['source_prob']*100:.1f}% "
                    f"× weight={c['weight']:.2f} × 0.20 = +{c['contribution']*100:.1f}%"
                )
        lines.append("")

    # ── Centrality ────────────────────────────────────────────────
    centrality = global_data.get("centrality", {})
    if centrality:
        lines.append("  THEATER CENTRALITY (Strategic Importance)")
        lines.append("  " + "-" * 55)
        sorted_c = sorted(centrality.items(), key=lambda x: -x[1])[:10]
        for cc, score in sorted_c:
            bar = "█" * int(score * 5)
            lines.append(f"    {cc:6s}  {score:.2f}  {bar}")
        lines.append("")

    # ── Collection Priority ───────────────────────────────────────
    coll_priority = global_data.get("collection_priority", [])
    if coll_priority:
        lines.append("  AUTONOMOUS COLLECTION PRIORITY")
        lines.append("  " + "-" * 55)
        for cc, score in coll_priority[:5]:
            lines.append(f"    {cc:6s}  priority={score:.4f}")
        lines.append("")

    return "\n".join(lines)
