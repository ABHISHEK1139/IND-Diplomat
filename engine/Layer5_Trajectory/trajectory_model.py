"""
Layer5_Trajectory — Bayesian + Logistic Hybrid Trajectory Model
================================================================

Models:
    P(HIGH in 14 days | Current State, Drift, Pressure)

Using:
    Posterior = Bayesian Prior × Logistic Transition Pressure

Design:
    - Logistic handles transition pressure smoothly
    - Bayesian preserves memory of previous escalation state
    - Linear models break under volatility — avoided

Phase 5 ONLY.  Never touches SRE core, domain fusion, or gate logic.
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("Layer5_Trajectory.trajectory_model")

# ── SRE history file ──────────────────────────────────────────────────
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_SRE_HISTORY_PATH = os.path.join(_DATA_DIR, "sre_history.json")

# ── Logistic steepness (governs transition sharpness) ─────────────────
LOGISTIC_STEEPNESS = 4.0

# ── Pressure blend weights ────────────────────────────────────────────
W_VELOCITY   = 0.35
W_STRUCTURAL = 0.35
W_NARRATIVE  = 0.30

# ── Trajectory blend weights ──────────────────────────────────────────
W_TRAJ_VELOCITY   = 0.35
W_TRAJ_PRESSURE   = 0.35
W_TRAJ_NDI        = 0.30

# ── Stability safeguards ─────────────────────────────────────────────
MAX_PROB_WITHOUT_MOB = 0.85   # cap unless mobilization_conf > 0.60
VELOCITY_BRAKE       = 0.85   # multiply prob_up if velocity < 0
COST_BRAKE           = 0.90   # multiply prob_up if cost > 0.70
PRE_WAR_NDI_THRESH   = 0.65
PRE_WAR_INTENT_THRESH = 0.50
PRE_WAR_BOOST        = 0.08

# ── Expansion thresholds ─────────────────────────────────────────────
EXPANSION_HIGH_THRESH   = 0.60
EXPANSION_MEDIUM_THRESH = 0.45


@dataclass
class TrajectoryResult:
    """Output of the trajectory model."""
    # Core probabilities
    prob_up: float = 0.0           # P(move to HIGH in 14 days)
    prob_down: float = 0.0         # P(move to LOW in 14 days)
    prob_stable: float = 1.0       # P(stay at current level)

    # Components
    prior: float = 0.0
    velocity: float = 0.0
    structural_pressure: float = 0.0
    narrative_drift: float = 0.0
    transition_factor: float = 0.5
    pressure_score: float = 0.0

    # Expansion & warnings
    expansion_mode: str = "NONE"
    pre_war_warning: bool = False
    acceleration_watch: bool = False

    # SRE context
    current_sre: float = 0.0
    current_risk: str = "LOW"

    def to_dict(self) -> dict:
        return {
            "prob_up": round(self.prob_up, 4),
            "prob_down": round(self.prob_down, 4),
            "prob_stable": round(self.prob_stable, 4),
            "prior": round(self.prior, 4),
            "velocity": round(self.velocity, 4),
            "structural_pressure": round(self.structural_pressure, 4),
            "narrative_drift": round(self.narrative_drift, 4),
            "transition_factor": round(self.transition_factor, 4),
            "pressure_score": round(self.pressure_score, 4),
            "expansion_mode": self.expansion_mode,
            "pre_war_warning": self.pre_war_warning,
            "acceleration_watch": self.acceleration_watch,
            "current_sre": round(self.current_sre, 4),
            "current_risk": self.current_risk,
        }


# ── SRE History Management ───────────────────────────────────────────

def _load_sre_history() -> List[float]:
    """Load historical SRE values (most recent last)."""
    try:
        if os.path.exists(_SRE_HISTORY_PATH):
            with open(_SRE_HISTORY_PATH, "r") as f:
                data = json.load(f)
            return [float(v) for v in data.get("values", [])]
    except Exception as exc:
        logger.warning("[TRAJECTORY] Failed to load SRE history: %s", exc)
    return []


def _save_sre_history(values: List[float]) -> None:
    """Persist SRE history (keep last 10 values)."""
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        trimmed = values[-10:]  # keep last 10
        with open(_SRE_HISTORY_PATH, "w") as f:
            json.dump({
                "values": trimmed,
                "updated": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)
    except Exception as exc:
        logger.warning("[TRAJECTORY] Failed to save SRE history: %s", exc)


# ── Step 2.1: Base Prior from SRE ─────────────────────────────────────

def base_prior_from_sre(sre: float) -> float:
    """
    Map current SRE to a baseline prior probability.

    This is not the final probability — it is the Bayesian prior
    that gets updated by the logistic transition factor.
    """
    if sre >= 0.75:
        return 0.75
    elif sre >= 0.55:
        return 0.55
    elif sre >= 0.40:
        return 0.40
    elif sre >= 0.25:
        return 0.25
    else:
        return 0.15


# ── Step 2.3: Logistic sigmoid ────────────────────────────────────────

def logistic(x: float) -> float:
    """Logistic sigmoid with configurable steepness."""
    return 1.0 / (1.0 + math.exp(-LOGISTIC_STEEPNESS * x))


# ── Step 2.4: Bayesian update ─────────────────────────────────────────

def bayesian_update(prior: float, transition_factor: float) -> float:
    """
    Bayesian posterior update.

    posterior_up = prior × transition_factor
    posterior_down = (1 - prior) × (1 - transition_factor)
    normalizer = posterior_up + posterior_down
    prob_up = posterior_up / normalizer
    """
    posterior_up = prior * transition_factor
    posterior_down = (1.0 - prior) * (1.0 - transition_factor)
    normalizer = posterior_up + posterior_down
    if normalizer <= 0:
        return prior
    return posterior_up / normalizer


# ── Main trajectory computation ───────────────────────────────────────

def compute_trajectory(
    current_sre: float,
    current_risk: str,
    sre_domains: dict,
    escalation_patterns: int = 0,
    spike_count: int = 0,
    trend_bonus: float = 0.0,
    ndi_result=None,
    mobilization_conf: float = 0.0,
    cost: float = 0.0,
    intent: float = 0.0,
    p_active_14d: float = 0.0,
) -> TrajectoryResult:
    """
    Compute 14-day escalation trajectory.

    Parameters
    ----------
    current_sre : float
        Current SRE escalation score.
    current_risk : str
        Current risk level (LOW/ELEVATED/HIGH/CRITICAL).
    sre_domains : dict
        Domain scores from compute_domain_indices().
    escalation_patterns : int
        Number of detected escalation patterns.
    spike_count : int
        Number of detected spikes.
    trend_bonus : float
        Current trend bonus from SRE.
    ndi_result : NarrativeDriftResult, optional
        Output from narrative_index.compute_narrative_drift().
    mobilization_conf : float
        SIG_MIL_MOBILIZATION confidence.
    cost : float
        Cost dimension score (inverted — high = low constraint).
    intent : float
        Intent dimension score.
    p_active_14d : float
        P(ACTIVE_CONFLICT + FULL_WAR) from Bayesian conflict state
        14-day forecast.  If > 0.6, adds +0.10 structural pressure
        (state → trajectory coupling).

    Returns
    -------
    TrajectoryResult
    """
    result = TrajectoryResult()
    result.current_sre = current_sre
    result.current_risk = current_risk

    # ── Step 2.1: Base prior ──────────────────────────────────────
    prior = base_prior_from_sre(current_sre)
    result.prior = prior

    # ── Step 4: Escalation velocity ───────────────────────────────
    history = _load_sre_history()
    history.append(current_sre)
    _save_sre_history(history)

    if len(history) >= 3:
        prev_avg = sum(history[-3:-1]) / 2.0
        velocity = current_sre - prev_avg
    elif len(history) >= 2:
        velocity = current_sre - history[-2]
    else:
        velocity = 0.0

    # Normalize velocity to [-1, +1] range (±0.3 SRE change = ±1.0)
    velocity = max(-1.0, min(1.0, velocity / 0.3))
    result.velocity = velocity

    # ── Step 5: Structural pressure ───────────────────────────────
    esc_pat_norm = min(1.0, escalation_patterns / 5.0)
    cost_raw = sre_domains.get("cost_raw", 0.0)
    structural_pressure = (
        0.5 * trend_bonus
        + 0.3 * esc_pat_norm
        + 0.2 * (1.0 - cost_raw)
    )

    # ── State → Trajectory coupling ──────────────────────────────
    # If the Bayesian conflict state model forecasts >60% chance of
    # ACTIVE_CONFLICT or FULL_WAR in 14 days, inject +0.10 into
    # structural pressure so the trajectory model reflects that.
    if p_active_14d > 0.60:
        structural_pressure += 0.10
        logger.info(
            "[TRAJECTORY] State→Trajectory coupling: P(ACTIVE+ 14d)=%.3f > 0.60 → +0.10 structural",
            p_active_14d,
        )

    structural_pressure = max(0.0, min(1.0, structural_pressure))
    result.structural_pressure = structural_pressure

    # ── Step 3: Narrative drift ───────────────────────────────────
    ndi = 0.0
    if ndi_result is not None:
        ndi = getattr(ndi_result, "ndi", 0.0)
    result.narrative_drift = ndi

    # ── Step 2.2: Transition pressure ─────────────────────────────
    pressure_score = (
        W_VELOCITY * velocity
        + W_STRUCTURAL * structural_pressure
        + W_NARRATIVE * ndi
    )
    pressure_score = max(-1.0, min(1.0, pressure_score))
    result.pressure_score = pressure_score

    # ── Step 2.3: Logistic transformation ─────────────────────────
    transition_factor = logistic(pressure_score)
    result.transition_factor = transition_factor

    # ── Step 2.4: Bayesian update ─────────────────────────────────
    prob_up = bayesian_update(prior, transition_factor)

    # ── Step 3: Pre-war structural trigger ────────────────────────
    pre_war = False
    if ndi > PRE_WAR_NDI_THRESH and intent > PRE_WAR_INTENT_THRESH and velocity > 0:
        prob_up += PRE_WAR_BOOST
        pre_war = True
        logger.info(
            "[TRAJECTORY] Pre-war trigger: NDI=%.3f intent=%.3f vel=%.3f → +%.2f",
            ndi, intent, velocity, PRE_WAR_BOOST,
        )

    # ── Step 5: Stability safeguards ──────────────────────────────
    if velocity < 0:
        prob_up *= VELOCITY_BRAKE
        logger.info("[TRAJECTORY] Velocity brake: vel=%.3f → prob_up ×%.2f", velocity, VELOCITY_BRAKE)

    if cost > 0.70:
        prob_up *= COST_BRAKE
        logger.info("[TRAJECTORY] Cost brake: cost=%.3f → prob_up ×%.2f", cost, COST_BRAKE)

    # Cap without confirmed mobilization
    if mobilization_conf <= 0.60:
        prob_up = min(prob_up, MAX_PROB_WITHOUT_MOB)

    prob_up = max(0.0, min(1.0, prob_up))

    # ── Probability of moving DOWN ────────────────────────────────
    prob_down = max(0.0, min(1.0,
        max(0.0, -0.4 * velocity)
        + 0.3 * cost_raw
        - 0.2 * ndi
    ))

    # Normalize: total probability budget
    prob_stable = max(0.0, 1.0 - prob_up - prob_down)

    result.prob_up = prob_up
    result.prob_down = prob_down
    result.prob_stable = prob_stable
    result.pre_war_warning = pre_war

    # ── Step 4: Expansion mode ────────────────────────────────────
    if prob_up >= EXPANSION_HIGH_THRESH:
        result.expansion_mode = "HIGH"
    elif prob_up >= EXPANSION_MEDIUM_THRESH:
        result.expansion_mode = "MEDIUM"
    else:
        result.expansion_mode = "NONE"

    # ── Tiered acceleration detection (Phase 8.1 upgrade) ───────
    try:
        from engine.Layer5_Trajectory.acceleration_detector import detect_acceleration
        _accel_result = detect_acceleration(
            current_velocity=velocity,
            ndi=ndi,
        )
        result.acceleration_watch = _accel_result.triggered
        result.acceleration_result = _accel_result   # full detail
    except Exception as _accel_exc:
        logger.warning("[TRAJECTORY] Acceleration detector failed: %s", _accel_exc)
        result.acceleration_watch = (velocity > 0 and ndi > 0.40)

    logger.info(
        "[TRAJECTORY] prior=%.3f  vel=%.3f  pressure=%.3f  NDI=%.3f  "
        "transition=%.3f  → P(HIGH 14d)=%.1f%%  P(LOW 14d)=%.1f%%  "
        "expansion=%s  pre_war=%s  accel_watch=%s",
        prior, velocity, structural_pressure, ndi,
        transition_factor, prob_up * 100, prob_down * 100,
        result.expansion_mode, pre_war, result.acceleration_watch,
    )

    return result
