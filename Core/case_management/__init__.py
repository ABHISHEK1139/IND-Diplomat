"""
Case management package.

Maintains persistent investigation cases and their memory trail.
"""

from .case import CaseRecord, CaseStatus
from .case_store import CaseStore
from .case_manager import CaseManager, case_manager

__all__ = [
    "CaseRecord",
    "CaseStatus",
    "CaseStore",
    "CaseManager",
    "case_manager",
]

