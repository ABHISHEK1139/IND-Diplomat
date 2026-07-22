"""
NextGen: Meta-Cognitive Self Model
==================================
Tracks system drift, predictive accuracy, and heuristic confidence decay over time.
Provides empirical introspection to the system.
"""

from typing import Dict, Any, List
import json
import logging
from pathlib import Path
from dip.Config.config import DATA_DIR

logger = logging.getLogger("NextGen.self_model")

# Alias for tests
SelfModel = None # Will be defined below

class AgentSelfModel:
    def __init__(self, data_path: Path = None):

        self.data_path = data_path or (DATA_DIR / "self_model" / "accuracy_log.json")
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.history = self._load_history()
        self.confidence_decay = 0.0
        self.recalibrate()

    def _load_history(self) -> List[Dict[str, Any]]:
        if self.data_path.exists():
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load self-model history: {e}")
                return []
        return []

    def log_result(self, prediction_id: str, expected_state: str, actual_state: str, confidence: float):
        """Logs a prediction result against reality (Backtesting outcome)."""
        is_correct = (expected_state == actual_state)
        
        record = {
            "prediction_id": prediction_id,
            "expected_state": expected_state,
            "actual_state": actual_state,
            "is_correct": is_correct,
            "original_confidence": confidence
        }
        
        self.history.append(record)
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=2)
            
        self.recalibrate()
        
    def recalibrate(self):
        """Adjusts confidence penalty (decay) based on recent predictive accuracy."""
        if not self.history:
            self.confidence_decay = 0.0
            return
            
        # Analyze last 50 predictions
        recent = self.history[-50:]
        correct = sum(1 for r in recent if r["is_correct"])
        accuracy = correct / len(recent)
        
        # If accuracy drops below 80%, increase decay
        if accuracy < 0.8:
            # Scale decay linearly up to 0.3 max penalty
            self.confidence_decay = min(0.3, (0.8 - accuracy))
        else:
            self.confidence_decay = 0.0
            
    def apply_decay(self, base_confidence: float) -> float:
        """Applies the current empirical confidence decay penalty."""
        return max(0.0, base_confidence - self.confidence_decay)
SelfModel = AgentSelfModel
