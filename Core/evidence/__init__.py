"""
Signal-level provenance helpers for evidence-backed reporting.
"""

from Core.evidence.provenance_tracker import Evidence, ProvenanceTracker
from Core.evidence.corroboration_engine import (
    corroboration_boost,
    diversity_factor,
    apply_corroboration,
    score_belief_corroboration,
    score_projected_signals,
    generate_corroboration_report,
    CorroborationReport,
)

__all__ = [
    "Evidence",
    "ProvenanceTracker",
    "corroboration_boost",
    "diversity_factor",
    "apply_corroboration",
    "score_belief_corroboration",
    "score_projected_signals",
    "generate_corroboration_report",
    "CorroborationReport",
]
