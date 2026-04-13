"""
Backwards‑compatibility shim.

Legacy tests import ``Layer4_Analysis.core.coordinator.Coordinator``.
The canonical class is ``Layer4_Analysis.coordinator.CouncilCoordinator``.
"""

from engine.Layer4_Analysis.coordinator import CouncilCoordinator as Coordinator  # noqa: F401

__all__ = ["Coordinator"]
