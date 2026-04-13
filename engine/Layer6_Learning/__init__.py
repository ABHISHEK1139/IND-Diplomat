"""
Layer6_Learning — Autonomous Strategic Core
=============================================

Phase 6: The system learns from its own predictions.

Modules
-------
forecast_archive       — persist every forecast with country tag
forecast_resolution    — compare predictions against outcomes (Brier)
calibration_engine     — aggregate Brier scores, interpret quality
auto_adjuster          — adjust SRE / trajectory weights within safety caps
confidence_recalibrator — apply calibration bonus to final confidence
learning_report        — format the PHASE 6 report section
"""

from engine.Layer6_Learning.forecast_archive import record_forecast, load_history
from engine.Layer6_Learning.forecast_resolution import resolve_forecasts
from engine.Layer6_Learning.calibration_engine import calibration_score, calibration_report
from engine.Layer6_Learning.auto_adjuster import compute_adjustments, apply_adjustments
from engine.Layer6_Learning.confidence_recalibrator import calibration_bonus
from engine.Layer6_Learning.learning_report import format_learning_section

__all__ = [
    "record_forecast",
    "load_history",
    "resolve_forecasts",
    "calibration_score",
    "calibration_report",
    "compute_adjustments",
    "apply_adjustments",
    "calibration_bonus",
    "format_learning_section",
]
