"""
Phase 6.5 — Confidence Recalibrator
=====================================

Applies a calibration bonus (or penalty) to the final confidence
score based on aggregate Brier performance.

Formula
-------
    confidence = base_confidence * (0.8 + 0.2 * (1 - avg_brier))

Interpretation
--------------
  Perfect forecaster (Brier=0):   ×1.00  (no change)
  Random forecaster  (Brier=0.25): ×0.95  (−5%)
  Bad forecaster     (Brier=0.50): ×0.90  (−10%)

Only activates when MIN_RESOLVED forecasts have been resolved.
Until then, the multiplier is 1.0 (neutral).
"""

from __future__ import annotations

import logging
from typing import Optional

from engine.Layer6_Learning.calibration_engine import (
    calibration_score,
    MIN_RESOLVED,
)

logger = logging.getLogger("Layer6_Learning.confidence_recalibrator")


def calibration_bonus(country: Optional[str] = None) -> float:
    """Compute the confidence multiplier based on calibration quality.

    Parameters
    ----------
    country : str or None
        If provided, use per-country Brier.  If None, use global.

    Returns
    -------
    float
        Multiplier in [0.80, 1.00].  Multiply ``base_confidence``
        by this value.
    """
    cal = calibration_score(country)

    if not cal["eligible"] or cal["avg_brier"] is None:
        logger.info(
            "[RECAL] Insufficient data (%d/%d resolved) — multiplier=1.0",
            cal["n_resolved"], MIN_RESOLVED,
        )
        return 1.0

    avg_brier = cal["avg_brier"]
    multiplier = 0.8 + 0.2 * (1.0 - avg_brier)
    multiplier = round(max(0.80, min(1.0, multiplier)), 6)

    logger.info(
        "[RECAL] avg_brier=%.4f → multiplier=%.4f  (tier=%s)",
        avg_brier, multiplier, cal["tier"],
    )
    return multiplier
