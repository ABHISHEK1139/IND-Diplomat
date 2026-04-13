"""
Report Builder — Output generation helpers.

Facade over ``Layer4_Analysis.pipeline.output_builder`` and
``CouncilCoordinator.generate_result`` / ``_collect_output_sources``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("Layer4_Analysis.coordinator_modules.report_builder")

# Re-export the pipeline builders unchanged
from engine.Layer4_Analysis.pipeline.output_builder import (
    build_council_reasoning_dict,
    serialize_hypotheses,
    build_withheld_output,
    build_approved_output,
)


def generate_report(session: Any) -> Any:
    """
    Generate the final AnalysisResult from a completed session.

    Wraps ``CouncilCoordinator.generate_result``.
    """
    from engine.Layer4_Analysis.coordinator import CouncilCoordinator
    coord = CouncilCoordinator()
    return coord.generate_result(session)


def collect_output_sources(session: Any) -> List[Dict[str, Any]]:
    """
    Collect evidence sources for the output bundle.

    Wraps ``CouncilCoordinator._collect_output_sources``.
    """
    from engine.Layer4_Analysis.coordinator import CouncilCoordinator
    coord = CouncilCoordinator()
    return coord._collect_output_sources(session)
