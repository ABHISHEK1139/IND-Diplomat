"""Layer-3 interface package."""

from .state_provider import (
    evaluate_precursors,
    get_analysis_readiness,
    get_state_context,
    get_state_context_dict,
)

__all__ = [
    "get_state_context",
    "get_state_context_dict",
    "evaluate_precursors",
    "get_analysis_readiness",
]
