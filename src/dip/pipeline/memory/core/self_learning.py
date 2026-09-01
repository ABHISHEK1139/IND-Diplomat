"""
Self-Directed Learning + Forecast Resolution + Reflection Log
==============================================================

Port of DIP_8 engine/Layer6_Learning/* modules.
Implements the autonomous learning loop: observe → reflect → experiment → remember.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

logger = logging.getLogger("Layer6_Learning")

LEARNING_PATH = Path(__file__).resolve().parent.parent / "data" / "learning_state.json"


class SelfDirectedLearning:
    """Autonomous learning loop from DIP_8 + A3.0 patterns."""
    
    def __init__(self):
        self.learning_goals: List[Dict[str, Any]] = []
        self.experiments: List[Dict[str, Any]] = []
        self.lessons: List[Dict[str, Any]] = []
        self._load()
    
    def _load(self) -> None:
        if LEARNING_PATH.exists():
            try:
                with open(LEARNING_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.learning_goals = data.get("goals", [])
                self.lessons = data.get("lessons", [])
            except Exception:
                pass
    
    def _save(self) -> None:
        LEARNING_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LEARNING_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "goals": self.learning_goals,
                "lessons": self.lessons[-100:],
                "updated": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)
    
    def observe(self, assessment_result: Dict[str, Any]) -> Dict[str, Any]:
        """Observe: extract what happened from an assessment."""
        return {
            "threat_level": assessment_result.get("threat_level"),
            "verification_score": assessment_result.get("verification_score", 0),
            "status": assessment_result.get("status"),
            "sre_score": (assessment_result.get("nextgen_sre") or {}).get("sre_escalation_score", 0),
        }
    
    def reflect(self, observation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Reflect: identify what worked and what didn't."""
        reflections = []
        if observation["status"] == "WITHHELD":
            reflections.append({
                "type": "gap_detected",
                "detail": "Assessment was WITHHELD — intelligence gaps present.",
                "action": "Improve collection on missing signals.",
            })
        if observation["verification_score"] < 0.5:
            reflections.append({
                "type": "low_confidence",
                "detail": f"Verification score {observation['verification_score']:.2f} below threshold.",
                "action": "Strengthen evidence corroboration pipeline.",
            })
        return reflections
    
    def choose_goal(self, reflections: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Choose next learning goal based on reflections."""
        if not reflections:
            return None
        top = reflections[0]
        goal = {
            "objective": top["action"],
            "trigger": top["detail"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "planned",
        }
        self.learning_goals.append(goal)
        self._save()
        return goal
    
    def remember_lesson(self, lesson: Dict[str, Any]) -> None:
        """Store a reusable lesson."""
        lesson["stored_at"] = datetime.now(timezone.utc).isoformat()
        self.lessons.append(lesson)
        self._save()
    
    def get_pending_goals(self) -> List[Dict[str, Any]]:
        return [g for g in self.learning_goals if g["status"] == "planned"]


class ForecastArchive:
    """Tracks forecasts and resolves them against reality."""
    
    def __init__(self):
        self.forecasts: List[Dict[str, Any]] = []
        self.resolutions: List[Dict[str, Any]] = []
    
    def record_forecast(self, query: str, country: str, predicted_level: str, confidence: float) -> str:
        fid = f"F_{len(self.forecasts)}_{int(datetime.now(timezone.utc).timestamp())}"
        self.forecasts.append({
            "id": fid,
            "query": query,
            "country": country,
            "predicted_level": predicted_level,
            "confidence": confidence,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "resolved": False,
        })
        return fid
    
    def resolve(self, forecast_id: str, actual_level: str) -> Dict[str, Any]:
        """Resolve a forecast against reality."""
        for f in self.forecasts:
            if f["id"] == forecast_id:
                f["resolved"] = True
                f["actual_level"] = actual_level
                f["correct"] = f["predicted_level"] == actual_level
                f["resolved_at"] = datetime.now(timezone.utc).isoformat()
                self.resolutions.append(f)
                return f
        return {"error": "forecast not found"}
    
    def get_calibration(self) -> Dict[str, Any]:
        resolved = [f for f in self.forecasts if f.get("resolved")]
        if not resolved:
            return {"calibrated": False, "message": "No resolved forecasts yet."}
        accuracy = sum(1 for f in resolved if f.get("correct")) / len(resolved)
        avg_confidence = np.mean([f["confidence"] for f in resolved])
        return {
            "forecasts_total": len(self.forecasts),
            "forecasts_resolved": len(resolved),
            "accuracy": round(accuracy, 4),
            "avg_confidence": round(avg_confidence, 4),
            "calibration_delta": round(accuracy - avg_confidence, 4),
        }


class ReflectionLog:
    """Durable reflection journal."""
    
    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or (Path(__file__).resolve().parent.parent / "data" / "reflection_log.json"))
        self.entries: List[Dict[str, Any]] = []
        self._load()
    
    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.entries = json.load(f)
            except Exception:
                pass
    
    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.entries[-200:], f, indent=2)
    
    def log(self, event: str, detail: Dict[str, Any]) -> None:
        self.entries.append({
            "event": event,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save()
    
    def recent(self, n: int = 10) -> List[Dict[str, Any]]:
        return self.entries[-n:]


# Singletons
self_directed_learning = SelfDirectedLearning()
forecast_archive = ForecastArchive()
reflection_log = ReflectionLog()
