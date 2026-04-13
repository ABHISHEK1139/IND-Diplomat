"""
Evidence View — Section 1 of the Intelligence Briefing
========================================================

Renders the observed signals and sensor data into a human-readable
evidence summary.  Camera rule: reads the assessment record, never
computes intelligence.
"""

from __future__ import annotations

from typing import Any, Dict, List


def render(record: Dict[str, Any]) -> str:
    """
    Render Section 1: Empirical Evidence Base.

    Reads ``record["observations"]`` and ``record["beliefs"]``.
    """
    obs = record.get("observations", {})
    beliefs = record.get("beliefs", [])

    lines: List[str] = []
    lines.append("## Section 1 — Empirical Evidence Base")
    lines.append("")

    # Sensor overview
    sensor = obs.get("sensor_score", 0.0)
    sig_count = obs.get("signal_count", 0)
    stale = obs.get("stale_signals", [])
    lines.append(f"**Sensor Score:** {sensor:.3f}  |  "
                 f"**Signals Detected:** {sig_count}  |  "
                 f"**Stale Signals:** {len(stale)}")
    lines.append("")

    if stale:
        lines.append("*Stale signals (may not reflect current conditions):*")
        for s in stale[:10]:
            lines.append(f"  - {s}")
        lines.append("")

    # Projected signals
    projected = obs.get("projected_signals", {})
    if projected:
        lines.append("### Projected Signal Matrix")
        lines.append("")
        lines.append("| Dimension | Signals |")
        lines.append("|-----------|---------|")
        for dim, sigs in projected.items():
            sig_list = ", ".join(sigs) if isinstance(sigs, list) else str(sigs)
            lines.append(f"| {dim} | {sig_list} |")
        lines.append("")

    # Matched signals
    matched = obs.get("matched_signals", [])
    if matched:
        lines.append(f"### Matched Signals ({len(matched)})")
        lines.append("")
        for sig in matched[:20]:
            lines.append(f"  - {sig}")
        lines.append("")

    # Minister beliefs (hypothesis coverage)
    # Phase 8: Also check council minister_positions for predicted signal
    # counts, since hypotheses may not always carry predicted_signals.
    council = record.get("council", {})
    minister_preds: Dict[str, int] = {}
    for mp in council.get("minister_positions", []):
        _mn = mp.get("minister", "")
        _ps = mp.get("predicted_signals", [])
        if _mn and _ps:
            minister_preds[_mn] = len(_ps)

    if beliefs:
        lines.append("### Minister Hypothesis Coverage")
        lines.append("")
        lines.append("| Minister | Dimension | Coverage | Predicted | Matched | Missing |")
        lines.append("|----------|-----------|----------|-----------|---------|---------|")
        for b in beliefs:
            minister = b.get("minister", "?")
            dim = b.get("dimension", "?")
            coverage = b.get("coverage", 0.0)
            n_pred = len(b.get("predicted_signals", []))
            # Phase 8: fallback to council minister_positions count
            if n_pred == 0:
                n_pred = minister_preds.get(minister, 0)
            n_match = len(b.get("matched_signals", []))
            n_miss = len(b.get("missing_signals", []))
            lines.append(f"| {minister} | {dim} | {coverage:.0%} | {n_pred} | {n_match} | {n_miss} |")
        lines.append("")

    return "\n".join(lines)
