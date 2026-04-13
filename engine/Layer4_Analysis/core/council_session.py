"""
Backwards‑compatibility shim.

Legacy tests import ``Layer4_Analysis.core.council_session.CouncilSession``.
The canonical class is ``Layer4_Analysis.council_session.CouncilSession``.
"""

from engine.Layer4_Analysis.council_session import CouncilSession  # noqa: F401
from engine.Layer4_Analysis.council_session import MinisterReport   # noqa: F401
from engine.Layer4_Analysis.council_session import SessionStatus    # noqa: F401

__all__ = ["CouncilSession", "MinisterReport", "SessionStatus"]
