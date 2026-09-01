"""
Self-Directed Learning Engine (Layer 6)
=======================================
Turns runtime friction into explicit learning goals.
"""

import os
import json
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone
from dip.core.schema import LearningReport

logger = logging.getLogger("Memory.learning")


class LearningEngine:
    def __init__(self):
        self.memory_path = os.path.join(os.path.dirname(__file__), "..", "data", "learning", "learning_memory.json")
        self.max_active_goals = 25
        self._initialize_memory()

    def _initialize_memory(self):
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        if not os.path.exists(self.memory_path):
            with open(self.memory_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "accuracy_history": [],
                    "confidence_calibration": 1.0,
                    "blind_spots": [],
                    "goals": []
                }, f)

    def _load(self) -> dict:
        try:
            with open(self.memory_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"accuracy_history": [], "confidence_calibration": 1.0, "blind_spots": [], "goals": []}

    def _save(self, data: dict):
        with open(self.memory_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def learn_from_session(self, session_result: dict) -> LearningReport:
        memory = self._load()
        report = LearningReport()
        
        # Simple heuristics for reflection based on session output
        status = session_result.get("status")
        verification = session_result.get("verification_score", 0.0)
        
        if status == "HUMAN_REVIEW":
            memory["blind_spots"].append("HIGH threat with LOW verification. Needs better source data.")
            memory["goals"].append({
                "id": f"G_{int(datetime.now(timezone.utc).timestamp())}",
                "description": "Improve verification scoring for high-threat scenarios",
                "priority": 0.8,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "active"
            })
            report.improvement_suggestions.append("Identify more reliable sources for military escalation.")
            
        if verification < 0.4:
            # Overconfident?
            memory["confidence_calibration"] *= 0.95
            report.improvement_suggestions.append("Reduce base confidence; system is generating unverified claims.")
            
        # Prune goals
        active_goals = [g for g in memory["goals"] if g["status"] == "active"]
        if len(active_goals) > self.max_active_goals:
            active_goals.sort(key=lambda x: x["priority"], reverse=True)
            active_goals = active_goals[:self.max_active_goals]
        memory["goals"] = active_goals
        
        report.confidence_adjustment = round(memory["confidence_calibration"], 2)
        report.blind_spots = list(set(memory["blind_spots"][-5:]))
        
        self._save(memory)
        return report

    def get_improvement_suggestions(self) -> List[str]:
        memory = self._load()
        active = [g["description"] for g in memory["goals"] if g["status"] == "active"]
        return active
