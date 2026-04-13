"""
Risk Engine — Escalation risk computation helpers.

Re-exports domain fusion, escalation index, and SRE helpers
as a clean module-level API.  Does NOT modify the originals.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Layer4_Analysis.coordinator_modules.risk_engine")

# Re-export existing core functions unchanged
from engine.Layer4_Analysis.domain_fusion import compute_domain_indices
from engine.Layer4_Analysis.escalation_index import (
    compute_escalation_index,
    escalation_to_risk,
    EscalationInput,
)


def compute_escalation_risk(
    session: Any,
) -> Tuple[str, float]:
    """
    Compute full escalation risk for a session.

    Wraps ``CouncilCoordinator.compute_escalation()`` and also
    returns the numeric score.

    Returns
    -------
    tuple[str, float]
        (risk_level, escalation_score)
    """
    from engine.Layer4_Analysis.coordinator import CouncilCoordinator

    coord = CouncilCoordinator()
    risk_level = coord.compute_escalation(session)
    _, driver, constraint = coord._net_escalation_score(session)
    return risk_level, driver - constraint


def net_escalation_score(session: Any) -> Tuple[float, float, float]:
    """
    Get (net, driver, constraint) scores.

    Wraps ``CouncilCoordinator._net_escalation_score``.
    """
    from engine.Layer4_Analysis.coordinator import CouncilCoordinator
    coord = CouncilCoordinator()
    return coord._net_escalation_score(session)


def driver_score_from_dimensions(dimensions: Dict[str, float]) -> float:
    """
    Compute the driver score from SRE dimension values.

    Wraps the static method without instantiating a coordinator.
    """
    from engine.Layer4_Analysis.coordinator import CouncilCoordinator
    return CouncilCoordinator._driver_score_from_dimensions(dimensions)
