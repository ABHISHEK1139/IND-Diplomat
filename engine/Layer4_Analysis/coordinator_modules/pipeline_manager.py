"""
Pipeline Manager — Thin entry point wrapping CouncilCoordinator.process_query.

This is the single function external callers use instead of
instantiating CouncilCoordinator directly.

Does NOT modify coordinator.py — wraps it.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("Layer4_Analysis.coordinator_modules.pipeline_manager")


async def run_pipeline(
    query: str,
    *,
    state_context: Any = None,
    country_code: str = "",
    max_investigation_loops: int = 1,
    **kwargs,
) -> Dict[str, Any]:
    """
    Run the full Layer-4 analysis pipeline.

    Wraps ``CouncilCoordinator.process_query`` without modifying
    the coordinator source.

    Parameters
    ----------
    query : str
        The analyst query (e.g. "Assess risk of …").
    state_context : StateContext, optional
        Pre-built state context.  If ``None``, coordinator builds one.
    country_code : str
        ISO-3 country code for the target theater.
    max_investigation_loops : int
        Max CRAG investigation cycles.

    Returns
    -------
    dict
        Full analysis result dictionary.
    """
    from engine.Layer4_Analysis.coordinator import CouncilCoordinator

    coordinator = CouncilCoordinator()
    result = await coordinator.process_query(
        query,
        state_context=state_context,
        max_investigation_loops=max_investigation_loops,
        **kwargs,
    )
    return result
