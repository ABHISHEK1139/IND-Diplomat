"""
Investigation Control Loop (ICL)
================================
This module serves as the central brain between the World Model (Layer 3) and Reasoning (Layer 4).
It evaluates readiness, identifies gaps, generates RFIs, and recursively executes targeted research.
"""

from .investigation_controller import InvestigationController
from .readiness_engine import evaluate_readiness
from .gap_analyzer import analyze_gaps
from .rfi_generator import generate_rfis

__all__ = ["InvestigationController", "evaluate_readiness", "analyze_gaps", "generate_rfis"]
