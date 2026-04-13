"""
Investigation bridge between state modeling and external collection.
"""

from .gap_detector import EVIDENCE_REQUIREMENTS, detect_gaps, detect_gap_report
from .investigation_planner import generate_queries, call_planner_llm
from .research_controller import (
    InvestigationOutcome,
    InvestigationController,
    run_investigation,
)
from .planner import generate_queries as planner_generate_queries
from .investigation_controller import run_investigation as controller_run_investigation

__all__ = [
    "EVIDENCE_REQUIREMENTS",
    "detect_gaps",
    "detect_gap_report",
    "generate_queries",
    "call_planner_llm",
    "InvestigationOutcome",
    "InvestigationController",
    "run_investigation",
    "planner_generate_queries",
    "controller_run_investigation",
]
