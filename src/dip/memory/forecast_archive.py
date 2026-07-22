"""
Forecast Archive (Layer 6)
==========================
Stores predictions and evaluates them against reality.
"""

import json
import os
import logging
from typing import Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger("Memory.forecast_archive")


class ForecastArchive:
    def __init__(self):
        self.archive_path = os.path.join(os.path.dirname(__file__), "..", "data", "forecasts", "forecast_archive.json")
        os.makedirs(os.path.dirname(self.archive_path), exist_ok=True)
        if not os.path.exists(self.archive_path):
            self._save({"forecasts": []})

    def _load(self) -> dict:
        try:
            with open(self.archive_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"forecasts": []}

    def _save(self, data: dict):
        with open(self.archive_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def record_forecast(self, query: str, country: str, predicted_level: str, confidence: float):
        data = self._load()
        forecast = {
            "id": f"F_{int(datetime.now(timezone.utc).timestamp())}",
            "query": query,
            "country": country,
            "predicted_level": predicted_level,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "resolved": False,
            "actual_level": None,
            "accuracy_score": None
        }
        data["forecasts"].append(forecast)
        self._save(data)

    def resolve_forecast(self, forecast_id: str, actual_level: str) -> float:
        data = self._load()
        score = 0.0
        for f in data["forecasts"]:
            if f["id"] == forecast_id and not f["resolved"]:
                f["resolved"] = True
                f["actual_level"] = actual_level
                
                # Simple exact match for now
                if f["predicted_level"] == actual_level:
                    score = 1.0
                elif (f["predicted_level"] in ["HIGH", "CRITICAL"]) and (actual_level in ["HIGH", "CRITICAL"]):
                    score = 0.8
                else:
                    score = 0.0
                    
                f["accuracy_score"] = score
                break
        self._save(data)
        return score

    def get_calibration_stats(self) -> Dict[str, Any]:
        data = self._load()
        resolved = [f for f in data["forecasts"] if f.get("resolved")]
        
        if not resolved:
            return {
                "total_forecasts": len(data["forecasts"]),
                "resolved_count": 0,
                "accuracy": 0.0,
                "avg_confidence": 0.0,
                "calibration_error": 0.0
            }
            
        avg_acc = sum(f["accuracy_score"] for f in resolved) / len(resolved)
        avg_conf = sum(f["confidence"] for f in resolved) / len(resolved)
        
        return {
            "total_forecasts": len(data["forecasts"]),
            "resolved_count": len(resolved),
            "accuracy": round(avg_acc, 3),
            "avg_confidence": round(avg_conf, 3),
            "calibration_error": round(abs(avg_acc - avg_conf), 3)
        }
