"""
Calibration Engine (Layer 6)
============================
Adjusts confidence weights based on historical accuracy.
"""

from dip.pipeline.memory.core.forecast_archive import ForecastArchive
import logging

logger = logging.getLogger("Memory.calibration")


class CalibrationEngine:
    def __init__(self):
        self.archive = ForecastArchive()

    def compute_adjustment(self) -> float:
        stats = self.archive.get_calibration_stats()
        if stats["resolved_count"] < 5:
            return 1.0  # Not enough data
            
        acc = stats["accuracy"]
        conf = stats["avg_confidence"]
        
        # If overconfident (conf > acc + margin)
        if conf > (acc + 0.15):
            return 0.85  # Reduce by 15%
            
        # If underconfident (acc > conf + margin)
        if acc > (conf + 0.15):
            return 1.10  # Increase by 10%
            
        return 1.0

    def get_calibration_report(self) -> dict:
        stats = self.archive.get_calibration_stats()
        adj = self.compute_adjustment()
        status = "WELL_CALIBRATED"
        if adj < 1.0: status = "OVERCONFIDENT"
        elif adj > 1.0: status = "UNDERCONFIDENT"
        
        return {
            "stats": stats,
            "recommended_adjustment": adj,
            "status": status
        }
