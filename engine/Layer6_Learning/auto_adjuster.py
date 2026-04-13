"""
Phase 6.4 — Auto-Threshold Adjustment
=======================================

When the calibration engine detects MISCALIBRATED (Brier ≥ 0.25),
this module adjusts SRE and trajectory weights within strict
safety caps.

Adjustable Constants
--------------------
From escalation_index.py:
    TREND_BONUS_CAP         (default 0.20)
    SPIKE_SEVERITY_WEIGHT   (default 0.02)
    TREND_BONUS_PER_PATTERN (default 0.04)
    TREND_BONUS_PER_SPIKE   (default 0.03)

From domain_fusion.py:
    RHETORICAL_INTENT_CAP   (default 0.60)

From trajectory_model.py:
    W_VELOCITY              (default 0.35)
    W_STRUCTURAL            (default 0.35)
    W_NARRATIVE             (default 0.30)

Safety
------
  ±20% max cumulative drift on any single constant.
  MIN_RESOLVED = 20 required before any adjustment activates.
  Adjustments are persisted to ``data/calibration_adjustments.json``
  and loaded at startup.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Dict, Optional

from engine.Layer6_Learning.calibration_engine import (
    calibration_score,
    MIN_RESOLVED,
    TIER_EXCELLENT,
    TIER_ACCEPTABLE,
)

logger = logging.getLogger("Layer6_Learning.auto_adjuster")

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_ADJUSTMENTS_PATH = os.path.join(_DATA_DIR, "calibration_adjustments.json")

_file_lock = threading.Lock()

# ── Safety cap: max ±20% drift from baseline ─────────────────────
MAX_DRIFT_RATIO = 0.20

# ── Baseline values (factory defaults) ───────────────────────────
BASELINES = {
    # escalation_index.py
    "TREND_BONUS_CAP":         0.20,
    "SPIKE_SEVERITY_WEIGHT":   0.02,
    "TREND_BONUS_PER_PATTERN": 0.04,
    "TREND_BONUS_PER_SPIKE":   0.03,
    # domain_fusion.py
    "RHETORICAL_INTENT_CAP":   0.60,
    # trajectory_model.py
    "W_VELOCITY":              0.35,
    "W_STRUCTURAL":            0.35,
    "W_NARRATIVE":             0.30,
}

# ── Step sizes for adjustment per miscalibration cycle ───────────
# MISCALIBRATED  (Brier ≥ 0.25):  reduce confidence-boosters,
#                                  dampen trend sensitivity
# EXCELLENT      (Brier < 0.15):  slightly increase structural weights
MISCALIBRATED_DELTAS = {
    "TREND_BONUS_CAP":         -0.01,   # reduce trend cap
    "SPIKE_SEVERITY_WEIGHT":   -0.002,  # dampen spike contribution
    "TREND_BONUS_PER_PATTERN": -0.005,  # reduce pattern bonus
    "TREND_BONUS_PER_SPIKE":   -0.003,  # reduce spike bonus
    "RHETORICAL_INTENT_CAP":   -0.03,   # tighten rhetorical cap
    "W_VELOCITY":               0.0,    # no change
    "W_STRUCTURAL":             0.02,   # increase structural weight
    "W_NARRATIVE":             -0.02,   # decrease narrative weight
}

EXCELLENT_DELTAS = {
    "TREND_BONUS_CAP":          0.005,  # relax trend cap slightly
    "SPIKE_SEVERITY_WEIGHT":    0.001,  # allow more spike contribution
    "TREND_BONUS_PER_PATTERN":  0.002,  # increase pattern bonus
    "TREND_BONUS_PER_SPIKE":    0.002,  # increase spike bonus
    "RHETORICAL_INTENT_CAP":    0.02,   # relax rhetorical cap
    "W_VELOCITY":               0.0,    # no change
    "W_STRUCTURAL":             0.0,    # no change
    "W_NARRATIVE":              0.0,    # no change
}


def compute_adjustments(country: Optional[str] = None) -> Dict[str, any]:
    """Compute what adjustments should be made (if any).

    Does NOT apply them — call ``apply_adjustments()`` to activate.

    Returns
    -------
    dict
        {
            "eligible": bool,
            "tier": str,
            "avg_brier": float|None,
            "proposed_deltas": dict,   # constant_name → delta
            "current_values": dict,    # constant_name → current value
            "reason": str,
        }
    """
    cal = calibration_score(country)
    tier = cal["tier"]
    eligible = cal["eligible"]

    if not eligible:
        return {
            "eligible": False,
            "tier": tier,
            "avg_brier": cal["avg_brier"],
            "proposed_deltas": {},
            "current_values": _load_current_values(),
            "reason": f"Insufficient data: {cal['n_resolved']}/{MIN_RESOLVED} resolved",
        }

    current = _load_current_values()

    if tier == "MISCALIBRATED":
        proposed = _clamp_deltas(current, MISCALIBRATED_DELTAS)
        reason = f"Brier={cal['avg_brier']:.4f} ≥ {TIER_ACCEPTABLE} — reducing trend sensitivity"
    elif tier == "EXCELLENT":
        proposed = _clamp_deltas(current, EXCELLENT_DELTAS)
        reason = f"Brier={cal['avg_brier']:.4f} < {TIER_EXCELLENT} — slight weight increase"
    else:
        proposed = {}
        reason = f"Brier={cal['avg_brier']:.4f} — ACCEPTABLE, no adjustment needed"

    return {
        "eligible": True,
        "tier": tier,
        "avg_brier": cal["avg_brier"],
        "proposed_deltas": proposed,
        "current_values": current,
        "reason": reason,
    }


def apply_adjustments(force: bool = False) -> Dict[str, float]:
    """Load persisted adjustments and apply them to module constants.

    Called once at the start of each analysis cycle.

    Parameters
    ----------
    force : bool
        If True, recompute and persist new adjustments before loading.
        Normally False — adjustments are computed separately and
        persisted by ``save_adjustments()``.

    Returns
    -------
    dict   Current effective values for all adjustable constants.
    """
    if force:
        adj = compute_adjustments()
        if adj["eligible"] and adj["proposed_deltas"]:
            current = adj["current_values"]
            for name, delta in adj["proposed_deltas"].items():
                current[name] = round(current.get(name, BASELINES[name]) + delta, 6)
            _save_values(current)
            logger.info(
                "[AUTO-ADJUST] Applied %d adjustments (tier=%s)",
                len(adj["proposed_deltas"]), adj["tier"],
            )

    values = _load_current_values()
    _inject_into_modules(values)
    return values


def save_adjustments(values: Dict[str, float]) -> None:
    """Persist adjusted values to disk."""
    _save_values(values)


def get_current_values() -> Dict[str, float]:
    """Return the currently active constant values."""
    return _load_current_values()


def get_drift_report() -> Dict[str, dict]:
    """Show drift from baseline for each constant.

    Returns
    -------
    dict
        constant_name → {"baseline": float, "current": float,
                         "drift_pct": float, "at_cap": bool}
    """
    current = _load_current_values()
    report = {}
    for name, baseline in BASELINES.items():
        cur = current.get(name, baseline)
        if baseline != 0:
            drift_pct = round((cur - baseline) / baseline * 100, 2)
        else:
            drift_pct = 0.0
        report[name] = {
            "baseline": baseline,
            "current": cur,
            "drift_pct": drift_pct,
            "at_cap": abs(drift_pct) >= MAX_DRIFT_RATIO * 100 - 0.01,
        }
    return report


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Internal
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _clamp_deltas(
    current: Dict[str, float],
    deltas: Dict[str, float],
) -> Dict[str, float]:
    """Apply deltas with ±20% safety cap enforcement.

    Returns only the deltas that are actually applicable
    (non-zero and within cap).
    """
    applicable = {}
    for name, delta in deltas.items():
        if delta == 0:
            continue
        baseline = BASELINES[name]
        cur = current.get(name, baseline)
        proposed = cur + delta
        # Enforce ±20% from baseline
        lo = baseline * (1 - MAX_DRIFT_RATIO)
        hi = baseline * (1 + MAX_DRIFT_RATIO)
        clamped = max(lo, min(hi, proposed))
        actual_delta = round(clamped - cur, 6)
        if abs(actual_delta) > 1e-8:
            applicable[name] = actual_delta
    return applicable


def _inject_into_modules(values: Dict[str, float]) -> None:
    """Push adjusted values into the live module constants.

    This modifies module-level variables so that the current
    analysis cycle uses the adjusted values.
    """
    import engine.Layer4_Analysis.escalation_index as eidx
    import engine.Layer5_Trajectory.trajectory_model as traj

    # escalation_index
    if "TREND_BONUS_CAP" in values:
        eidx.TREND_BONUS_CAP = values["TREND_BONUS_CAP"]
    if "SPIKE_SEVERITY_WEIGHT" in values:
        eidx.SPIKE_SEVERITY_WEIGHT = values["SPIKE_SEVERITY_WEIGHT"]
    if "TREND_BONUS_PER_PATTERN" in values:
        eidx.TREND_BONUS_PER_PATTERN = values["TREND_BONUS_PER_PATTERN"]
    if "TREND_BONUS_PER_SPIKE" in values:
        eidx.TREND_BONUS_PER_SPIKE = values["TREND_BONUS_PER_SPIKE"]

    # trajectory_model
    if "W_VELOCITY" in values:
        traj.W_VELOCITY = values["W_VELOCITY"]
    if "W_STRUCTURAL" in values:
        traj.W_STRUCTURAL = values["W_STRUCTURAL"]
    if "W_NARRATIVE" in values:
        traj.W_NARRATIVE = values["W_NARRATIVE"]

    # domain_fusion — rhetorical cap is used inline, so we store
    # it as a module-level override that domain_fusion reads.
    if "RHETORICAL_INTENT_CAP" in values:
        try:
            import engine.Layer4_Analysis.domain_fusion as dfus
            dfus._RHETORICAL_INTENT_CAP_OVERRIDE = values["RHETORICAL_INTENT_CAP"]
        except Exception:
            pass

    logger.info(
        "[AUTO-ADJUST] Injected %d constants into live modules",
        len(values),
    )


def _load_current_values() -> Dict[str, float]:
    """Load persisted adjustments or return baselines."""
    with _file_lock:
        if not os.path.exists(_ADJUSTMENTS_PATH):
            return dict(BASELINES)
        try:
            with open(_ADJUSTMENTS_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                # Merge with baselines to ensure all keys present
                merged = dict(BASELINES)
                merged.update(data)
                return merged
            return dict(BASELINES)
        except (json.JSONDecodeError, IOError):
            return dict(BASELINES)


def _save_values(values: Dict[str, float]) -> None:
    with _file_lock:
        os.makedirs(os.path.dirname(_ADJUSTMENTS_PATH), exist_ok=True)
        with open(_ADJUSTMENTS_PATH, "w", encoding="utf-8") as fh:
            json.dump(values, fh, indent=2)
