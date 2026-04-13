"""
War Probability Composite Index (WPCI)
=======================================

Fuses four independent probability channels into a single calibrated
war-probability estimate:

    WPCI = w_sre × SRE + w_cs × P(ACTIVE+) + w_traj × P(HIGH 14d) + w_nar × NDI

Default weights  (sum = 1.0):
    SRE         0.35  – quantitative escalation score
    ConflictSt  0.30  – Bayesian state classification (P ACTIVE_CONFLICT+)
    Trajectory  0.20  – logistic / Bayesian 14-day outlook
    Narrative   0.15  – GDELT narrative drift index

Output
------
A ``WPCIResult`` with the composite score mapped to a 5-tier verbal
label plus per-channel contributions for transparency.

Integration
-----------
Called from ``synthesis_engine._run_sre_pipeline`` after the trajectory
and black-swan blocks.  The result is stored as ``session.wpci_result``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger("Layer4_Analysis.war_index")

# ── Channel weights (sum = 1.0) ──────────────────────────────────
W_SRE       = 0.35
W_CONFLICT  = 0.30
W_TRAJ      = 0.20
W_NARRATIVE = 0.15

# ── Tier thresholds ───────────────────────────────────────────────
_TIERS = [
    (0.75, "CRITICAL",    "War onset indicators fully converged"),
    (0.55, "HIGH",        "Multiple channels signalling imminent conflict"),
    (0.35, "ELEVATED",    "Detectable acceleration across channels"),
    (0.18, "GUARDED",     "Low-level signals without convergence"),
    (0.00, "LOW",         "Baseline — no composite convergence"),
]

# ── Channel-divergence penalty ────────────────────────────────────
# If any single channel is > 0.50 but the composite is below ELEVATED,
# flag as DIVERGENT.  Prevents a single hot channel from being invisible.
_DIVERGENCE_SINGLE_THRESH = 0.50
_DIVERGENCE_COMPOSITE_THRESH = 0.35


@dataclass
class WPCIResult:
    """Output of the WPCI computation."""
    composite: float = 0.0
    tier: str = "LOW"
    tier_description: str = ""
    channels: Dict[str, float] = None  # type: ignore[assignment]
    divergent: bool = False
    dominant_channel: str = ""

    def __post_init__(self):
        if self.channels is None:
            self.channels = {}

    def to_dict(self) -> dict:
        return {
            "composite": round(self.composite, 4),
            "tier": self.tier,
            "tier_description": self.tier_description,
            "channels": {k: round(v, 4) for k, v in (self.channels or {}).items()},
            "divergent": self.divergent,
            "dominant_channel": self.dominant_channel,
        }


def compute_wpci(
    sre_score: float = 0.0,
    p_active_or_higher: float = 0.0,
    trajectory_prob_up: float = 0.0,
    ndi: float = 0.0,
) -> WPCIResult:
    """
    Compute the War Probability Composite Index.

    Parameters
    ----------
    sre_score : float
        Current SRE escalation score [0–1].
    p_active_or_higher : float
        Bayesian conflict state P(ACTIVE_CONFLICT + FULL_WAR) [0–1].
    trajectory_prob_up : float
        Trajectory model P(HIGH in 14 days) [0–1].
    ndi : float
        Narrative Drift Index [0–1].

    Returns
    -------
    WPCIResult
    """
    # Clamp inputs
    sre = max(0.0, min(1.0, float(sre_score)))
    cs  = max(0.0, min(1.0, float(p_active_or_higher)))
    tj  = max(0.0, min(1.0, float(trajectory_prob_up)))
    nd  = max(0.0, min(1.0, float(ndi)))

    # Weighted fusion
    composite = (
        W_SRE      * sre
        + W_CONFLICT * cs
        + W_TRAJ     * tj
        + W_NARRATIVE * nd
    )
    composite = max(0.0, min(1.0, composite))

    channels = {
        "sre": sre,
        "conflict_state": cs,
        "trajectory": tj,
        "narrative": nd,
    }

    # Tier mapping
    tier = "LOW"
    tier_desc = ""
    for threshold, label, desc in _TIERS:
        if composite >= threshold:
            tier = label
            tier_desc = desc
            break

    # Dominant channel
    weighted = {
        "sre": W_SRE * sre,
        "conflict_state": W_CONFLICT * cs,
        "trajectory": W_TRAJ * tj,
        "narrative": W_NARRATIVE * nd,
    }
    dominant = max(weighted, key=weighted.get)  # type: ignore[arg-type]

    # Divergence detection
    divergent = False
    if composite < _DIVERGENCE_COMPOSITE_THRESH:
        if any(v >= _DIVERGENCE_SINGLE_THRESH for v in channels.values()):
            divergent = True

    result = WPCIResult(
        composite=composite,
        tier=tier,
        tier_description=tier_desc,
        channels=channels,
        divergent=divergent,
        dominant_channel=dominant,
    )

    logger.info(
        "[WPCI] composite=%.3f  tier=%s  dom=%s  divergent=%s | "
        "sre=%.3f cs=%.3f traj=%.3f ndi=%.3f",
        composite, tier, dominant, divergent, sre, cs, tj, nd,
    )

    return result
