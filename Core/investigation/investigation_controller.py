"""
Compatibility wrapper for investigation controller naming.
"""

from .research_controller import (
    InvestigationOutcome,
    InvestigationController,
    investigation_controller,
    run_investigation,
)

__all__ = [
    "InvestigationOutcome",
    "InvestigationController",
    "investigation_controller",
    "run_investigation",
]
