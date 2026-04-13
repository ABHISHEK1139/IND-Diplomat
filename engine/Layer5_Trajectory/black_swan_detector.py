"""
Layer5_Trajectory — Black Swan Detector
========================================

Detects discontinuity events that invalidate smooth-trend assumptions.

Three independent detection channels:

    Channel 1: SPIKE SEVERITY
        max_spike_severity >= 3.5  →  A single burst of extreme magnitude.

    Channel 2: STRUCTURAL DISCONTINUITY
        |velocity| > 0.6  AND  transition_factor > 0.85
        → The trajectory model itself sees a phase transition.

    Channel 3: RARE HIGH-IMPACT SIGNAL
        One of {SIG_WMD_RISK, SIG_ALLIANCE_INVOCATION, SIG_MASS_MOBILIZATION,
        SIG_REGIME_COLLAPSE} with confidence > 0.85 AND recency > 0.9.
        → Historically decisive signals that rewrite the scenario.

Doctrinal design:
    A Black Swan trigger does NOT override everything instantly.
    It forces escalation seriousness while preserving human authority:

        - Escalation:  sre_esc += 0.20  (controlled, not maxed)
        - Trajectory:  prob_up = max(prob_up, 0.70); expansion = FORCED_HIGH
        - Gate:        Cannot WITHHOLD;  confidence capped at 0.60
        - Report:      Mandatory human review flag + explicit section

Phase 5.2 — integrated into existing Phase 5 trajectory pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Layer5_Trajectory.black_swan_detector")

# ── Channel 1: Spike severity threshold ──────────────────────────────
SPIKE_SEVERITY_THRESHOLD = 3.5

# ── Channel 2: Structural discontinuity ──────────────────────────────
VELOCITY_DISCONTINUITY   = 0.6     # |velocity| must exceed this
TRANSITION_DISCONTINUITY = 0.85    # transition_factor must exceed this

# ── Channel 3: Rare high-impact signals ──────────────────────────────
RARE_HIGH_IMPACT_SIGNALS = frozenset({
    "SIG_WMD_RISK",
    "SIG_ALLIANCE_INVOCATION",
    "SIG_MASS_MOBILIZATION",
    "SIG_REGIME_COLLAPSE",
})
RARE_SIGNAL_CONF_THRESHOLD    = 0.85
RARE_SIGNAL_RECENCY_THRESHOLD = 0.90

# ── Override parameters ──────────────────────────────────────────────
ESCALATION_BOOST     = 0.20   # added to SRE
TREND_BONUS_BOOST    = 0.15   # added to trend component
TRAJECTORY_PROB_FLOOR = 0.70  # min P(HIGH 14d)
CONFIDENCE_CAP       = 0.60   # gate confidence ceiling


@dataclass
class BlackSwanResult:
    """Output of the Black Swan detector."""

    triggered: bool = False
    reasons: List[str] = field(default_factory=list)
    channels_fired: List[str] = field(default_factory=list)

    # Override values (only meaningful when triggered=True)
    escalation_boost: float = 0.0
    trajectory_floor: float = 0.0
    confidence_cap: float = 1.0
    mandatory_review: bool = False

    def to_dict(self) -> dict:
        return {
            "triggered": self.triggered,
            "reasons": list(self.reasons),
            "channels_fired": list(self.channels_fired),
            "escalation_boost": round(self.escalation_boost, 4),
            "trajectory_floor": round(self.trajectory_floor, 4),
            "confidence_cap": round(self.confidence_cap, 4),
            "mandatory_review": self.mandatory_review,
        }


def detect(
    *,
    max_spike_severity: float = 0.0,
    velocity: float = 0.0,
    transition_factor: float = 0.5,
    projected_signals: Optional[Dict[str, Any]] = None,
    systemic_cascade: bool = False,
) -> BlackSwanResult:
    """
    Run all three Black Swan detection channels.

    Parameters
    ----------
    max_spike_severity : float
        Maximum sigma-score across current spikes (from EscalationInput).
    velocity : float
        SRE velocity from trajectory model (normalized to [-1, +1]).
    transition_factor : float
        Logistic transition factor from trajectory model.
    projected_signals : dict, optional
        Map of signal_name → projection object.  Each projection must
        expose ``confidence`` (float) and ``recency`` (float) attributes.

    Returns
    -------
    BlackSwanResult
        ``triggered=True`` if any channel fires.
    """
    result = BlackSwanResult()
    projected_signals = projected_signals or {}

    # ── Channel 1: Spike severity ─────────────────────────────────
    if max_spike_severity >= SPIKE_SEVERITY_THRESHOLD:
        result.channels_fired.append("SPIKE_SEVERITY")
        result.reasons.append(
            f"Spike severity {max_spike_severity:.2f} >= "
            f"{SPIKE_SEVERITY_THRESHOLD} threshold — extreme burst detected"
        )
        logger.warning(
            "[BLACK_SWAN] Channel 1 FIRED: spike_severity=%.2f",
            max_spike_severity,
        )

    # ── Channel 2: Structural discontinuity ───────────────────────
    if abs(velocity) > VELOCITY_DISCONTINUITY and transition_factor > TRANSITION_DISCONTINUITY:
        result.channels_fired.append("STRUCTURAL_DISCONTINUITY")
        result.reasons.append(
            f"Structural discontinuity: |velocity|={abs(velocity):.3f} > "
            f"{VELOCITY_DISCONTINUITY} AND transition_factor="
            f"{transition_factor:.3f} > {TRANSITION_DISCONTINUITY} — "
            f"phase transition in progress"
        )
        logger.warning(
            "[BLACK_SWAN] Channel 2 FIRED: |vel|=%.3f, transition=%.3f",
            abs(velocity), transition_factor,
        )

    # ── Channel 3: Rare high-impact signal ────────────────────────
    for sig_name, proj in projected_signals.items():
        sig_upper = str(sig_name).upper()
        if sig_upper not in RARE_HIGH_IMPACT_SIGNALS:
            continue

        conf = float(getattr(proj, "confidence", 0.0) or 0.0)
        recency = float(getattr(proj, "recency", 0.0) or 0.0)

        if conf > RARE_SIGNAL_CONF_THRESHOLD and recency > RARE_SIGNAL_RECENCY_THRESHOLD:
            result.channels_fired.append(f"RARE_SIGNAL:{sig_upper}")
            result.reasons.append(
                f"Rare high-impact signal {sig_upper}: confidence="
                f"{conf:.3f} > {RARE_SIGNAL_CONF_THRESHOLD} AND recency="
                f"{recency:.3f} > {RARE_SIGNAL_RECENCY_THRESHOLD} — "
                f"historically decisive indicator confirmed"
            )
            logger.warning(
                "[BLACK_SWAN] Channel 3 FIRED: %s conf=%.3f recency=%.3f",
                sig_upper, conf, recency,
            )

    # ── Channel 4: Systemic Cascade (Phase 7) ────────────────────
    # Triggered when the sum of all theater SRE scores exceeds the
    # systemic cascade threshold (default 4.0). This means multiple
    # theaters are simultaneously at HIGH/CRITICAL — a world crisis.
    if systemic_cascade:
        result.channels_fired.append("SYSTEMIC_CASCADE")
        result.reasons.append(
            "Systemic cascade detected: aggregate global SRE exceeds "
            "threshold — multiple theaters in simultaneous crisis"
        )
        logger.warning(
            "[BLACK_SWAN] Channel 4 FIRED: SYSTEMIC_CASCADE — global contagion threshold breached"
        )

    # ── Aggregate result ──────────────────────────────────────────
    if result.channels_fired:
        result.triggered = True
        result.escalation_boost = ESCALATION_BOOST
        result.trajectory_floor = TRAJECTORY_PROB_FLOOR
        result.confidence_cap = CONFIDENCE_CAP
        result.mandatory_review = True

        logger.warning(
            "[BLACK_SWAN] TRIGGERED — %d channel(s): %s",
            len(result.channels_fired),
            ", ".join(result.channels_fired),
        )
    else:
        logger.info("[BLACK_SWAN] No discontinuity detected — all channels clear")

    return result


__all__ = [
    "BlackSwanResult",
    "detect",
    "ESCALATION_BOOST",
    "TREND_BONUS_BOOST",
    "TRAJECTORY_PROB_FLOOR",
    "CONFIDENCE_CAP",
]
