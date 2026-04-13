"""
Coordinator Modules — Facade over the monolithic CouncilCoordinator
====================================================================

Provides logical sub-module access without modifying coordinator.py.

Usage::

    from engine.Layer4_Analysis.coordinator_modules import (
        pipeline_manager,
        signal_pipeline,
        minister_engine,
        risk_engine,
        report_builder,
        calibration_engine,
        state_engine,
    )

Each module re-exports functions from the existing coordinator,
organized by responsibility.  The original coordinator.py
remains untouched and is still the canonical entry point.
"""

from engine.Layer4_Analysis.coordinator_modules.pipeline_manager import run_pipeline
from engine.Layer4_Analysis.coordinator_modules.signal_pipeline import (
    build_signal_belief_maps,
    ensure_pressure_derived_signals,
    observed_signals_from_beliefs,
    collect_missing_signals,
)
from engine.Layer4_Analysis.coordinator_modules.minister_engine import (
    convene_ministers,
    DEFAULT_HYPOTHESES,
)
from engine.Layer4_Analysis.coordinator_modules.risk_engine import (
    compute_escalation_risk,
    net_escalation_score,
    driver_score_from_dimensions,
)
from engine.Layer4_Analysis.coordinator_modules.report_builder import (
    generate_report,
    collect_output_sources,
)
from engine.Layer4_Analysis.coordinator_modules.calibration_engine import (
    calibrate_confidence,
    apply_red_team_penalty,
)
from engine.Layer4_Analysis.coordinator_modules.state_engine import (
    StateSnapshotStore,
    compute_trend_from_snapshots,
)

__all__ = [
    "run_pipeline",
    "build_signal_belief_maps",
    "ensure_pressure_derived_signals",
    "observed_signals_from_beliefs",
    "collect_missing_signals",
    "convene_ministers",
    "DEFAULT_HYPOTHESES",
    "compute_escalation_risk",
    "net_escalation_score",
    "driver_score_from_dimensions",
    "generate_report",
    "collect_output_sources",
    "calibrate_confidence",
    "apply_red_team_penalty",
    "StateSnapshotStore",
    "compute_trend_from_snapshots",
]
