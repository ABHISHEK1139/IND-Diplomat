"""
Replay Consolidation — Background Learning from Past Assessments
=================================================================

Autonomous_3.0 pattern: replays past assessments during idle time,
auto-calibrates thresholds and minister weights from replay results.

Port of DIP_8 self_directed_learning.py + A3.0 dream_scheduler.py
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

logger = logging.getLogger("Layer6_Learning.replay_consolidation")

REPLAY_PATH = Path(__file__).resolve().parent.parent / "data" / "replay_results.json"


class ReplayConsolidator:
    """Background replay and auto-calibration engine."""

    def __init__(self):
        self.replay_results: List[Dict[str, Any]] = []
        self.calibrated_thresholds: Dict[str, float] = {}
        self.minister_weights: Dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        if REPLAY_PATH.exists():
            try:
                with open(REPLAY_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.replay_results = data.get("results", [])
                self.calibrated_thresholds = data.get("thresholds", {})
                self.minister_weights = data.get("minister_weights", {})
            except Exception:
                pass

    def _save(self) -> None:
        REPLAY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(REPLAY_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "results": self.replay_results[-100:],
                "thresholds": self.calibrated_thresholds,
                "minister_weights": self.minister_weights,
                "updated": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)

    def record_replay(self, scenario: str, expected: str, actual: str, confidence: float) -> Dict[str, Any]:
        """Record a single replay result."""
        correct = expected == actual
        result = {
            "scenario": scenario,
            "expected": expected,
            "actual": actual,
            "confidence": confidence,
            "correct": correct,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.replay_results.append(result)
        self._consolidate()
        self._save()
        return result

    def _consolidate(self) -> None:
        """Auto-calibrate from replay results."""
        if len(self.replay_results) < 5:
            return

        accuracies = [r["confidence"] for r in self.replay_results]
        outcomes = [1 if r["correct"] else 0 for r in self.replay_results]

        # Calibrate confidence threshold
        avg_conf = np.mean(accuracies)
        actual_acc = np.mean(outcomes)
        delta = actual_acc - avg_conf

        if delta < -0.05:  # overconfident
            self.calibrated_thresholds["confidence_floor"] = min(0.65, self.calibrated_thresholds.get("confidence_floor", 0.55) + 0.02)
        elif delta > 0.05:  # underconfident
            self.calibrated_thresholds["confidence_floor"] = max(0.45, self.calibrated_thresholds.get("confidence_floor", 0.55) - 0.02)

    def get_calibrated_threshold(self, name: str, default: float = 0.55) -> float:
        """Get a calibrated threshold, falling back to default."""
        return self.calibrated_thresholds.get(name, default)

    def get_report(self) -> Dict[str, Any]:
        """Get consolidation report."""
        if not self.replay_results:
            return {"replays": 0, "message": "No replay data yet."}

        correct = sum(1 for r in self.replay_results if r["correct"])
        total = len(self.replay_results)

        return {
            "replays": total,
            "accuracy": round(correct / total, 4) if total > 0 else 0.0,
            "calibrated_thresholds": self.calibrated_thresholds,
            "minister_weights": self.minister_weights,
        }


_replay_consolidator: Optional[ReplayConsolidator] = None


def get_replay_consolidator() -> ReplayConsolidator:
    global _replay_consolidator
    if _replay_consolidator is None:
        _replay_consolidator = ReplayConsolidator()
    return _replay_consolidator

ReplayBuffer = ReplayConsolidator
