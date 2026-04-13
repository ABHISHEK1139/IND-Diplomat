"""Layer-3 State Model package.

Layer-3 responsibilities:
- measure and construct interpreted state
- score credibility/grounding
- expose a single interface for Layer-4
"""

from engine.Layer3_StateModel.interface.state_provider import (
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
