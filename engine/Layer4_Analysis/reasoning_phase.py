"""
Deterministic Layer-4 reasoning phases.
"""

from enum import Enum


class ReasoningPhase(Enum):
    INITIAL_DELIBERATION = "INITIAL_DELIBERATION"
    CHALLENGE = "CHALLENGE"
    INVESTIGATION = "INVESTIGATION"
    VERIFICATION = "VERIFICATION"
    SAFETY_REVIEW = "SAFETY_REVIEW"
    FINALIZED = "FINALIZED"
    FAILED = "FAILED"

