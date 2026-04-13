"""
Bias Detector — Appendix B of the Intelligence Briefing
=========================================================

Detects and reports potential analytical biases visible in the
assessment record.  These are structural checks, not intelligence
computation — the bias *exists* in the data; this module surfaces it.

Camera rule: reports only what it finds in the record.
"""

from __future__ import annotations

from typing import Any, Dict, List


def render(record: Dict[str, Any]) -> str:
    """
    Render Appendix B: Bias & Limitations Report.

    Reads multiple sections of the record to detect bias patterns.
    """
    beliefs = record.get("beliefs", [])
    obs = record.get("observations", {})
    risk = record.get("risk_engine", {})
    debate = record.get("council_debate", {})
    rt = record.get("red_team", {})
    legal = record.get("legal_analysis", {})

    lines: List[str] = []
    lines.append("## Appendix B — Bias & Limitations Report")
    lines.append("")

    findings: List[Dict[str, str]] = []

    # 1. Dimension concentration bias
    dim_counts: Dict[str, int] = {}
    for b in beliefs:
        d = b.get("dimension", "unknown")
        dim_counts[d] = dim_counts.get(d, 0) + 1
    if dim_counts:
        max_dim = max(dim_counts, key=dim_counts.get)  # type: ignore[arg-type]
        total_b = sum(dim_counts.values())
        if dim_counts[max_dim] / max(total_b, 1) > 0.5:
            findings.append({
                "bias": "Dimension Concentration",
                "detail": f"Over-represented dimension: **{max_dim}** "
                          f"({dim_counts[max_dim]}/{total_b} hypotheses). "
                          f"Assessment may under-weight other dimensions.",
                "severity": "MEDIUM",
            })

    # 2. Source diversity — all signals from one modality?
    stale = obs.get("stale_signals", [])
    sig_count = obs.get("signal_count", 0)
    if sig_count > 0 and len(stale) / max(sig_count, 1) > 0.4:
        findings.append({
            "bias": "Staleness Risk",
            "detail": f"{len(stale)}/{sig_count} signals are stale. "
                      f"Assessment may reflect past state, not current reality.",
            "severity": "HIGH",
        })

    # 3. Red team bypass — if assessment was not challenged
    if not rt.get("active", False):
        findings.append({
            "bias": "Unchallenged Assessment",
            "detail": "Red team was not activated.  Assessment has not undergone "
                      "adversarial scrutiny.  Confirmation bias risk.",
            "severity": "HIGH",
        })
    elif rt.get("is_robust", True) and not rt.get("contradictions"):
        findings.append({
            "bias": "Weak Adversarial Test",
            "detail": "Red team found no contradictions.  This may indicate "
                      "either genuine robustness or an insufficiently aggressive "
                      "challenge methodology.",
            "severity": "LOW",
        })

    # 4. Consensus bias — no conflicts in debate
    conflicts = debate.get("conflicts_surfaced", []) or debate.get("conflicts", [])
    positions = debate.get("minister_positions", [])
    if positions and not conflicts:
        findings.append({
            "bias": "Groupthink Risk",
            "detail": f"All {len(positions)} ministers reached consensus with "
                      f"no recorded conflicts.  May indicate insufficient "
                      f"diversity of analytical perspectives.",
            "severity": "MEDIUM",
        })

    # 5. Legal coverage gap
    legal_domains = legal.get("domains_covered", [])
    if not legal_domains:
        findings.append({
            "bias": "Legal Blind Spot",
            "detail": "No legal/treaty sources were consulted.  The assessment "
                      "lacks a legal constraint framework.",
            "severity": "MEDIUM",
        })

    # 6. Anchoring on sensor score
    sensor_conf = risk.get("confidence_breakdown", {}).get("sensor_confidence", 0.0)
    final = risk.get("final_confidence", 0.0)
    if final > 0 and abs(sensor_conf - final) < 0.05:
        findings.append({
            "bias": "Sensor Anchoring",
            "detail": "Final confidence is very close to raw sensor score.  "
                      "Other analytical components may not be contributing "
                      "meaningful correction.",
            "severity": "LOW",
        })

    # Render findings
    if not findings:
        lines.append("**No significant biases detected** in this assessment record.")
        lines.append("")
        lines.append("*Note: Absence of detected bias does not guarantee unbiased analysis.  "
                     "This check covers structural patterns only.*")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"**{len(findings)} potential bias(es) detected:**")
    lines.append("")
    lines.append("| # | Bias Type | Severity | Detail |")
    lines.append("|---|-----------|----------|--------|")
    for i, f in enumerate(findings, 1):
        lines.append(f"| {i} | {f['bias']} | {f['severity']} | {f['detail']} |")
    lines.append("")

    # Severity summary
    high = sum(1 for f in findings if f["severity"] == "HIGH")
    if high:
        lines.append(f"**{high} HIGH-severity bias(es)** require analyst attention "
                     f"before this assessment is disseminated.")
        lines.append("")

    return "\n".join(lines)
