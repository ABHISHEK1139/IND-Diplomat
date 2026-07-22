"""
Confidence Recalibrator — sklearn Calibration + Brier Score
=============================================================

Tracks predicted confidence vs actual outcomes. Uses sklearn's
calibration_curve and brier_score_loss to detect over/under-confidence.

If P(forecast) says 0.75 but actual rate is 0.40 → overconfident → adjust down.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger("Layer6_Learning.recalibrator")

try:
    from sklearn.calibration import calibration_curve
    from sklearn.metrics import brier_score_loss
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.info("sklearn not installed. Using numpy calibration fallback.")

CALIBRATION_PATH = Path(__file__).resolve().parent.parent / "data" / "calibration.json"


class ConfidenceRecalibrator:
    """Tracks and recalibrates confidence scores."""

    def __init__(self):
        self.predictions: List[Tuple[float, int]] = []  # (confidence, 0/1 outcome)
        self.calibration_multiplier: float = 1.0
        self.brier_score: float = 0.0
        self._load()

    def _load(self) -> None:
        if CALIBRATION_PATH.exists():
            try:
                with open(CALIBRATION_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.predictions = [(p[0], p[1]) for p in data.get("predictions", [])]
                self.calibration_multiplier = data.get("multiplier", 1.0)
                self.brier_score = data.get("brier_score", 0.0)
            except Exception:
                pass

    def _save(self) -> None:
        CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CALIBRATION_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "predictions": self.predictions[-1000:],
                "multiplier": self.calibration_multiplier,
                "brier_score": self.brier_score,
                "updated": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)

    def record(self, confidence: float, outcome: int) -> Dict[str, Any]:
        """Record a prediction-outcome pair.
        
        Args:
            confidence: Predicted confidence [0-1]
            outcome: 1 if correct, 0 if incorrect
        """
        self.predictions.append((confidence, outcome))
        self._recalibrate()
        self._save()
        return self.get_report()

    def _recalibrate(self) -> None:
        """Recalibrate using sklearn or numpy fallback."""
        if len(self.predictions) < 5:
            return

        confidences = np.array([p[0] for p in self.predictions])
        outcomes = np.array([p[1] for p in self.predictions])

        if SKLEARN_AVAILABLE:
            self.brier_score = float(brier_score_loss(outcomes, confidences))
            # Compute calibration multiplier: actual_rate / predicted_rate for top bin
            prob_true, prob_pred = calibration_curve(outcomes, confidences, n_bins=5)
            if len(prob_true) >= 2:
                # Ratio of actual to predicted in the high-confidence bin
                ratio = prob_true[-1] / max(0.01, prob_pred[-1])
                self.calibration_multiplier = round(
                    0.7 * self.calibration_multiplier + 0.3 * min(1.2, max(0.8, ratio)), 4
                )
        else:
            # Numpy fallback: mean squared error
            self.brier_score = float(np.mean((confidences - outcomes) ** 2))
            avg_conf = float(np.mean(confidences))
            avg_outcome = float(np.mean(outcomes))
            if avg_conf > 0:
                ratio = avg_outcome / avg_conf
                self.calibration_multiplier = round(
                    0.7 * self.calibration_multiplier + 0.3 * min(1.2, max(0.8, ratio)), 4
                )

    def adjust_confidence(self, raw_confidence: float) -> float:
        """Apply calibration multiplier to a raw confidence score."""
        return round(max(0.0, min(1.0, raw_confidence * self.calibration_multiplier)), 4)

    def get_report(self) -> Dict[str, Any]:
        """Get current calibration report."""
        if not self.predictions:
            return {"calibrated": False, "message": "Insufficient data for calibration."}

        confidences = np.array([p[0] for p in self.predictions])
        outcomes = np.array([p[1] for p in self.predictions])
        avg_conf = float(np.mean(confidences))
        avg_outcome = float(np.mean(outcomes))
        delta = avg_outcome - avg_conf

        return {
            "predictions_recorded": len(self.predictions),
            "average_confidence": round(avg_conf, 4),
            "actual_accuracy": round(avg_outcome, 4),
            "calibration_delta": round(delta, 4),
            "brier_score": round(self.brier_score, 4),
            "calibration_multiplier": self.calibration_multiplier,
            "status": "overconfident" if delta < -0.05 else "underconfident" if delta > 0.05 else "calibrated",
        }


_recalibrator: Optional[ConfidenceRecalibrator] = None


def get_recalibrator() -> ConfidenceRecalibrator:
    global _recalibrator
    if _recalibrator is None:
        _recalibrator = ConfidenceRecalibrator()
    return _recalibrator
