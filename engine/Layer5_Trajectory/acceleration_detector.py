"""
Escalation Acceleration Detector
=================================

Replaces the naïve boolean ``acceleration_watch`` with a tiered
alert system that tracks velocity history and computes acceleration
(second derivative of SRE).

Tiers
-----
NONE     – velocity stable or falling
WATCH    – velocity rising but acceleration modest
WARNING  – sustained positive acceleration (≥2 cycles)
CRITICAL – acceleration exceeding historical norm by ≥2σ

Integration
-----------
Called from ``trajectory_model.compute_trajectory`` after velocity
computation; the result replaces the old boolean ``acceleration_watch``.
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger("Layer5_Trajectory.acceleration_detector")

# ── Persistence ───────────────────────────────────────────────────
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_VELOCITY_HISTORY_PATH = os.path.join(_DATA_DIR, "velocity_history.json")

# ── Thresholds ────────────────────────────────────────────────────
_MIN_HISTORY = 3           # cycles before tiered detection activates
_WATCH_ACCEL = 0.05        # acceleration ≥ this → WATCH
_WARNING_STREAK = 2        # consecutive positive accels → WARNING
_CRITICAL_SIGMA = 2.0      # z-score of acceleration → CRITICAL
_SRE_BOOST_WATCH = 0.00    # no SRE boost at WATCH
_SRE_BOOST_WARNING = 0.03  # small SRE nudge at WARNING
_SRE_BOOST_CRITICAL = 0.07 # material SRE boost at CRITICAL
_MAX_HISTORY = 15          # trimmed to prevent unbounded growth


@dataclass
class AccelerationResult:
    """Output of the acceleration detector."""
    tier: str = "NONE"              # NONE | WATCH | WARNING | CRITICAL
    acceleration: float = 0.0      # second derivative of SRE
    velocity_trend: str = "STABLE" # RISING | FALLING | STABLE
    consecutive_positive: int = 0  # streak of positive accelerations
    z_score: float = 0.0           # acceleration z-score against history
    sre_boost: float = 0.0        # suggested SRE boost
    triggered: bool = False       # any tier above NONE

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "acceleration": round(self.acceleration, 5),
            "velocity_trend": self.velocity_trend,
            "consecutive_positive": self.consecutive_positive,
            "z_score": round(self.z_score, 3),
            "sre_boost": round(self.sre_boost, 4),
            "triggered": self.triggered,
        }


# ── Velocity history persistence ──────────────────────────────────

def _load_velocity_history() -> List[float]:
    try:
        if os.path.exists(_VELOCITY_HISTORY_PATH):
            with open(_VELOCITY_HISTORY_PATH, "r") as fh:
                data = json.load(fh)
            return [float(v) for v in data.get("values", [])]
    except Exception as exc:
        logger.warning("[ACCEL] Failed to load velocity history: %s", exc)
    return []


def _save_velocity_history(values: List[float]) -> None:
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        trimmed = values[-_MAX_HISTORY:]
        with open(_VELOCITY_HISTORY_PATH, "w") as fh:
            json.dump({
                "values": trimmed,
                "updated": datetime.now(timezone.utc).isoformat(),
            }, fh, indent=2)
    except Exception as exc:
        logger.warning("[ACCEL] Failed to save velocity history: %s", exc)


# ── Core detection ────────────────────────────────────────────────

def detect_acceleration(
    current_velocity: float,
    ndi: float = 0.0,
) -> AccelerationResult:
    """
    Compute escalation acceleration and return tiered alert.

    Parameters
    ----------
    current_velocity : float
        SRE velocity from ``compute_trajectory`` (normalised ±1.0).
    ndi : float
        Narrative Drift Index — high NDI amplifies concern.

    Returns
    -------
    AccelerationResult
    """
    result = AccelerationResult()

    # ── Persist current velocity ──────────────────────────────────
    history = _load_velocity_history()
    history.append(current_velocity)
    _save_velocity_history(history)

    if len(history) < _MIN_HISTORY:
        # Not enough data for tiered detection — fall back to simple check
        result.triggered = current_velocity > 0 and ndi > 0.40
        result.tier = "WATCH" if result.triggered else "NONE"
        return result

    # ── Acceleration (second derivative) ──────────────────────────
    accels: List[float] = []
    for i in range(2, len(history)):
        accels.append(history[i] - history[i - 1])

    current_accel = accels[-1] if accels else 0.0
    result.acceleration = current_accel

    # ── Velocity trend ────────────────────────────────────────────
    if current_velocity > 0.05:
        result.velocity_trend = "RISING"
    elif current_velocity < -0.05:
        result.velocity_trend = "FALLING"
    else:
        result.velocity_trend = "STABLE"

    # ── Consecutive positive accelerations (streak) ───────────────
    streak = 0
    for a in reversed(accels):
        if a > 0:
            streak += 1
        else:
            break
    result.consecutive_positive = streak

    # ── Z-score of current acceleration ───────────────────────────
    if len(accels) >= 3:
        mean_a = sum(accels) / len(accels)
        var_a = sum((a - mean_a) ** 2 for a in accels) / len(accels)
        std_a = math.sqrt(var_a) if var_a > 0 else 0.01
        result.z_score = (current_accel - mean_a) / std_a
    else:
        result.z_score = 0.0

    # ── Tiered classification ─────────────────────────────────────
    if result.z_score >= _CRITICAL_SIGMA and current_accel > _WATCH_ACCEL:
        result.tier = "CRITICAL"
        result.sre_boost = _SRE_BOOST_CRITICAL
    elif streak >= _WARNING_STREAK and current_accel > _WATCH_ACCEL:
        result.tier = "WARNING"
        result.sre_boost = _SRE_BOOST_WARNING
    elif current_accel >= _WATCH_ACCEL or (current_velocity > 0 and ndi > 0.40):
        result.tier = "WATCH"
        result.sre_boost = _SRE_BOOST_WATCH
    else:
        result.tier = "NONE"
        result.sre_boost = 0.0

    result.triggered = result.tier != "NONE"

    logger.info(
        "[ACCEL] tier=%s  accel=%.4f  z=%.2f  streak=%d  vel_trend=%s  sre_boost=%.3f",
        result.tier, current_accel, result.z_score, streak,
        result.velocity_trend, result.sre_boost,
    )
    return result
