"""
Online Drift Detector — Incremental Anomaly Detection
======================================================

Uses River (online ML) for streaming drift detection on SRE scores.
Falls back to numpy/zscore when River is unavailable.

Port of DIP_8 concept with A3.0 online learning pattern.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("Layer5_Trajectory.online_drift")

try:
    from river import anomaly, drift, stats
    RIVER_AVAILABLE = True
except ImportError:
    RIVER_AVAILABLE = False
    logger.info("River not installed. Using numpy fallback for drift detection.")


class OnlineDriftDetector:
    """Incrementally detects anomalies and concept drift in SRE scores.

    Each new data point updates the model. Drift is detected without
    retraining on the full dataset.
    """

    def __init__(self, window_size: int = 30):
        self.window_size = window_size
        self.values: deque = deque(maxlen=window_size)
        self.timestamps: deque = deque(maxlen=window_size)
        self.anomaly_count = 0
        self.total_count = 0

        if RIVER_AVAILABLE:
            self._hst = anomaly.HalfSpaceTrees(n_trees=10, height=5, window_size=window_size)
            self._adwin = drift.ADWIN()
            self._var = stats.Var()
        else:
            self._hst = None
            self._adwin = None
            self._var = None

    def update(self, timestamp: str, sre_score: float) -> Dict[str, Any]:
        """Update detector with a new observation. Returns drift/anomaly info."""
        self.total_count += 1
        self.values.append(sre_score)
        self.timestamps.append(timestamp)

        is_anomaly = False
        drift_detected = False
        z_score = 0.0

        if RIVER_AVAILABLE and self._hst is not None:
            # River-based detection
            self._hst.learn_one({"score": sre_score})
            is_anomaly = self._hst.score_one({"score": sre_score}) > 0.8

            if self._adwin is not None and len(self.values) >= 5:
                self._adwin.update(sre_score)
                drift_detected = self._adwin.drift_detected
        else:
            # Numpy fallback: z-score anomaly detection
            if len(self.values) >= 5:
                arr = np.array(self.values)
                mean = np.mean(arr)
                std = np.std(arr)
                if std > 0:
                    z_score = (sre_score - mean) / std
                    is_anomaly = abs(z_score) > 2.5
                    drift_detected = abs(z_score) > 3.0

        if is_anomaly:
            self.anomaly_count += 1

        return {
            "sre_score": sre_score,
            "is_anomaly": is_anomaly,
            "z_score": round(z_score, 3),
            "drift_detected": drift_detected,
            "anomaly_rate": round(self.anomaly_count / max(1, self.total_count), 4),
            "window_mean": round(float(np.mean(self.values)), 4),
            "window_std": round(float(np.std(self.values)), 4),
        }

    def get_state(self) -> Dict[str, Any]:
        """Export current detector state."""
        return {
            "total_observations": self.total_count,
            "anomaly_count": self.anomaly_count,
            "anomaly_rate": round(self.anomaly_count / max(1, self.total_count), 4),
            "current_mean": round(float(np.mean(self.values)), 4) if self.values else 0.0,
            "current_std": round(float(np.std(self.values)), 4) if self.values else 0.0,
        }


def detect_anomalies(score_history: List[Dict[str, Any]], window: int = 30) -> List[Dict[str, Any]]:
    """Batch detection: run all scores through the drift detector."""
    detector = OnlineDriftDetector(window_size=window)
    results = []
    for entry in score_history:
        result = detector.update(
            timestamp=str(entry.get("timestamp", "")),
            sre_score=float(entry.get("sre_score", 0.0)),
        )
        results.append(result)
    return results
