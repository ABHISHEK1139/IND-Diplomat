"""
Gap Reasoning Engine — structural gap and contradiction detection.

A real analyst does not just detect signals — they notice what's missing.

╔═══════════════════════════════════════════════════════════════════╗
║  "We see rhetoric and sanctions… but no logistics confirmation.  ║
║   That gap weakens escalation confidence."                       ║
║                                                                   ║
║  This module teaches the system to think that way.               ║
╚═══════════════════════════════════════════════════════════════════╝

Three capabilities:
  1. Structural gap detection — expected co-occurring signals
  2. Contradiction detection — mutually exclusive signals
  3. Penalty computation — feeds into confidence model

Author: Intelligence-grade reasoning upgrade (Block 3)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
#  EXPECTED SIGNAL PAIRS — "If A is strong, B should be present"
# ══════════════════════════════════════════════════════════════════════
# When signal A is strong (>= STRONG_THRESHOLD) but expected pair B
# is weak (<= WEAK_THRESHOLD), this is a structural gap.
#
# A real analyst sees mobilization without logistics and says:
# "This is suspicious — investigate."

EXPECTED_PAIRS: Dict[str, str] = {
    # Military escalation expects logistics preparation
    "SIG_MIL_ESCALATION":       "SIG_LOGISTICS_PREP",
    # Diplomatic hostility expects negotiation breakdown
    "SIG_DIP_HOSTILITY":        "SIG_NEGOTIATION_BREAKDOWN",
    # Mobilization expects force posture change
    "SIG_MIL_MOBILIZATION":     "SIG_FORCE_POSTURE",
    # Sanctions escalation expects economic pressure
    "SIG_SANCTIONS_ACTIVE":     "SIG_ECONOMIC_PRESSURE",
    # Coercive bargaining expects alliance activation
    "SIG_COERCIVE_BARGAINING":  "SIG_ALLIANCE_ACTIVATION",
    # Force posture expects cyber preparation (modern warfare)
    "SIG_FORCE_POSTURE":        "SIG_CYBER_ACTIVITY",
    # Kinetic activity expects confirmed mobilization
    "SIG_KINETIC_ACTIVITY":     "SIG_MIL_MOBILIZATION",
    # Retaliatory threat expects force posture
    "SIG_RETALIATORY_THREAT":   "SIG_FORCE_POSTURE",
}

# ══════════════════════════════════════════════════════════════════════
#  CONTRADICTIONS — signals that should NOT co-occur at high strength
# ══════════════════════════════════════════════════════════════════════
# If both signals in a pair are strong, something is inconsistent.
# Could mean: source conflict, rapidly changing situation, or error.

CONTRADICTIONS: List[Tuple[str, str]] = [
    # Active diplomacy contradicts negotiation breakdown
    ("SIG_DIPLOMACY_ACTIVE",        "SIG_NEGOTIATION_BREAKDOWN"),
    # Diplomacy active contradicts full hostility
    ("SIG_DIPLOMACY_ACTIVE",        "SIG_DIP_HOSTILITY"),
    # Deterrence signaling contradicts coercive pressure
    # (you either deter OR coerce — both at max is suspicious)
    ("SIG_DETERRENCE_SIGNALING",    "SIG_COERCIVE_PRESSURE"),
]

# ── Thresholds ─────────────────────────────────────────────────────
STRONG_THRESHOLD = 0.60    # Signal A must be above this
WEAK_THRESHOLD   = 0.20    # Expected pair B must be below this
CONTRADICTION_THRESHOLD = 0.55  # Both signals must be above this

# ── Penalties applied per finding ──────────────────────────────────
GAP_PENALTY_PER  = 0.03    # per structural gap
CONTRADICTION_PENALTY_PER = 0.05  # per contradiction
MAX_GAP_PENALTY  = 0.15    # cap total gap penalty
MAX_CONTRADICTION_PENALTY = 0.15  # cap total contradiction penalty


@dataclass
class GapReport:
    """Result of structural gap and contradiction analysis."""
    gaps: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    gap_count: int = 0
    contradiction_count: int = 0
    gap_penalty: float = 0.0
    contradiction_penalty: float = 0.0
    uncertainty_explanation: str = ""

    @property
    def total_penalty(self) -> float:
        return self.gap_penalty + self.contradiction_penalty

    @property
    def has_issues(self) -> bool:
        return self.gap_count > 0 or self.contradiction_count > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gaps": list(self.gaps),
            "contradictions": list(self.contradictions),
            "gap_count": self.gap_count,
            "contradiction_count": self.contradiction_count,
            "gap_penalty": round(self.gap_penalty, 4),
            "contradiction_penalty": round(self.contradiction_penalty, 4),
            "total_penalty": round(self.total_penalty, 4),
            "uncertainty_explanation": self.uncertainty_explanation,
        }


def _get_signal_confidence(signal_name: str, signal_conf: Dict[str, float]) -> float:
    """Extract signal confidence, checking multiple key formats."""
    # Direct match
    val = signal_conf.get(signal_name, None)
    if val is not None:
        return max(0.0, min(1.0, float(val)))
    # Try without SIG_ prefix, try lowercase
    for k, v in signal_conf.items():
        if k.upper() == signal_name.upper():
            return max(0.0, min(1.0, float(v)))
    return 0.0


def detect_structural_gaps(signal_conf: Dict[str, float]) -> List[str]:
    """
    Detect expected signals that are missing.

    Example output:
        ["SIG_MIL_ESCALATION (0.72) without SIG_LOGISTICS_PREP (0.05)"]
    """
    gaps: List[str] = []
    for signal_a, signal_b in EXPECTED_PAIRS.items():
        conf_a = _get_signal_confidence(signal_a, signal_conf)
        conf_b = _get_signal_confidence(signal_b, signal_conf)

        if conf_a >= STRONG_THRESHOLD and conf_b <= WEAK_THRESHOLD:
            gaps.append(
                f"{signal_a} ({conf_a:.2f}) without {signal_b} ({conf_b:.2f})"
            )
    return gaps


def detect_contradictions(signal_conf: Dict[str, float]) -> List[str]:
    """
    Detect contradictory signal pairs where both are strong.

    Example output:
        ["SIG_DIPLOMACY_ACTIVE (0.80) contradicts SIG_NEGOTIATION_BREAKDOWN (0.65)"]
    """
    found: List[str] = []
    for signal_a, signal_b in CONTRADICTIONS:
        conf_a = _get_signal_confidence(signal_a, signal_conf)
        conf_b = _get_signal_confidence(signal_b, signal_conf)

        if conf_a >= CONTRADICTION_THRESHOLD and conf_b >= CONTRADICTION_THRESHOLD:
            found.append(
                f"{signal_a} ({conf_a:.2f}) contradicts {signal_b} ({conf_b:.2f})"
            )
    return found


def analyse_gaps(signal_conf: Dict[str, float]) -> GapReport:
    """
    Full structural analysis: gaps + contradictions + penalties.

    Parameters
    ----------
    signal_conf : dict
        Signal name → confidence mapping (values in [0, 1]).

    Returns
    -------
    GapReport
        Report with findings, penalties, and uncertainty explanation.
    """
    gaps = detect_structural_gaps(signal_conf)
    contradictions = detect_contradictions(signal_conf)

    gap_penalty = min(len(gaps) * GAP_PENALTY_PER, MAX_GAP_PENALTY)
    contradiction_penalty = min(
        len(contradictions) * CONTRADICTION_PENALTY_PER,
        MAX_CONTRADICTION_PENALTY,
    )

    # Build human-readable uncertainty explanation
    explanation_parts: List[str] = []
    if gaps:
        gap_summaries = []
        for g in gaps:
            # Extract signal names for concise explanation
            parts = g.split(" without ")
            if len(parts) == 2:
                a_name = parts[0].split(" (")[0]
                b_name = parts[1].split(" (")[0]
                gap_summaries.append(f"missing {b_name} despite strong {a_name}")
            else:
                gap_summaries.append(g)
        explanation_parts.append(
            f"Structural gaps detected: {'; '.join(gap_summaries)}."
        )
    if contradictions:
        explanation_parts.append(
            f"{len(contradictions)} contradictory signal pair(s) found — "
            "source conflict or rapidly changing situation suspected."
        )
    if not explanation_parts:
        explanation = ""
    else:
        explanation = (
            "Assessment unstable: " + " ".join(explanation_parts)
        )

    report = GapReport(
        gaps=gaps,
        contradictions=contradictions,
        gap_count=len(gaps),
        contradiction_count=len(contradictions),
        gap_penalty=gap_penalty,
        contradiction_penalty=contradiction_penalty,
        uncertainty_explanation=explanation,
    )

    if report.has_issues:
        logger.info(
            "[GAP-ENGINE] %d structural gaps, %d contradictions — "
            "total penalty=%.3f",
            report.gap_count, report.contradiction_count,
            report.total_penalty,
        )
        for g in gaps:
            logger.info("[GAP-DETECTED] %s", g)
        for c in contradictions:
            logger.info("[CONTRADICTION] %s", c)

    return report
