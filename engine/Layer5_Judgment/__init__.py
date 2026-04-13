"""
Layer5_Judgment — Assessment Gate Authority
============================================

The council *analyzes*.  The gate *authorizes*.

This package exposes:
    - evaluate(state) → GateVerdict
    - build_assessment_state(session) → AssessmentState
    - AssessmentState, GateVerdict (dataclasses)
    - format_assessment(result) → str (intelligence report)
"""

from .assessment_gate import (  # noqa: F401
    AssessmentState,
    GateVerdict,
    evaluate,
    build_assessment_state,
)

from .report_formatter import (  # noqa: F401
    format_assessment,
    format_from_pipeline,
)

__all__ = [
    "AssessmentState",
    "GateVerdict",
    "evaluate",
    "build_assessment_state",
    "format_assessment",
    "format_from_pipeline",
]
