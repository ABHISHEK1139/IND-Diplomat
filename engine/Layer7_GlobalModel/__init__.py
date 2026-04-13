"""
Layer7_GlobalModel — Multi-Theater Strategic Synchronization
==============================================================

Phase 7: The system becomes a global strategic nervous system.

Modules
-------
global_state              — registry of all active theaters
interdependence_matrix    — geopolitical coupling strengths
contagion_engine          — shock propagation across states
cross_theater_forecaster  — spillover-adjusted probabilities
global_report             — PHASE 7 report section formatter
"""

from engine.Layer7_GlobalModel.global_state import (
    update_theater,
    get_theater,
    get_all_theaters,
    get_active_theaters,
    TheaterState,
)
from engine.Layer7_GlobalModel.contagion_engine import propagate_shock, propagate_all
from engine.Layer7_GlobalModel.cross_theater_forecaster import (
    adjusted_probability,
    global_risk_summary,
    global_black_swan,
    theater_centrality,
)
from engine.Layer7_GlobalModel.global_report import format_global_section

__all__ = [
    "update_theater",
    "get_theater",
    "get_all_theaters",
    "get_active_theaters",
    "TheaterState",
    "propagate_shock",
    "propagate_all",
    "adjusted_probability",
    "global_risk_summary",
    "global_black_swan",
    "theater_centrality",
    "format_global_section",
]
