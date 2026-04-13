"""
Phase 7.3 — Contagion Engine
===============================

When one theater's SRE rises sharply, propagate the effect to
coupled theaters via the interdependence matrix.

This creates second-order escalation risk:
    Iran escalation → Israel response → Lebanon mobilization

Design:
    - Contagion only flows FROM theaters with SRE > SHOCK_THRESHOLD
    - Spillover = shock_strength × coupling_weight × CONTAGION_DECAY
    - Results are additive to neighbor's contagion_received accumulator
    - Each cycle, contagion_received decays by 20% (stale prevention)
    - Contagion never raises a theater's SRE above 1.0
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from engine.Layer7_GlobalModel.global_state import (
    GLOBAL_THEATERS,
    get_active_theaters,
    decay_contagion,
    TheaterState,
)
from engine.Layer7_GlobalModel.interdependence_matrix import (
    get_neighbors,
    get_weight,
)

logger = logging.getLogger("Layer7_GlobalModel.contagion_engine")

# ── Configuration ────────────────────────────────────────────────
CONTAGION_DECAY = 0.25       # Spillover multiplier (dampening)
SHOCK_THRESHOLD = 0.30       # Minimum SRE to be a contagion source
CONTAGION_CYCLE_DECAY = 0.80 # Each cycle, old contagion fades by 20%


def propagate_shock(
    source_country: str,
    *,
    force_sre: Optional[float] = None,
) -> Dict[str, float]:
    """Propagate escalation contagion from a single source theater.

    Parameters
    ----------
    source_country : str
        ISO-3 code of the theater experiencing escalation.
    force_sre : float, optional
        Override source SRE (used for testing). If None, reads from
        GLOBAL_THEATERS.

    Returns
    -------
    dict
        Mapping of target_country → spillover amount applied.
    """
    cc = source_country.upper()
    source = GLOBAL_THEATERS.get(cc)
    if source is None:
        return {}

    shock_strength = force_sre if force_sre is not None else source.current_sre
    if shock_strength < SHOCK_THRESHOLD:
        return {}

    spillovers: Dict[str, float] = {}
    neighbors = get_neighbors(cc)

    for target_cc, weight in neighbors:
        target = GLOBAL_THEATERS.get(target_cc)
        if target is None:
            continue

        spillover = round(shock_strength * weight * CONTAGION_DECAY, 6)
        if spillover < 0.001:
            continue

        target.contagion_received = round(
            min(1.0, target.contagion_received + spillover), 6
        )
        spillovers[target_cc] = spillover

    if spillovers:
        logger.info(
            "[CONTAGION] %s (SRE=%.3f) → %d neighbors: %s",
            cc, shock_strength, len(spillovers),
            ", ".join(f"{k}+{v:.3f}" for k, v in spillovers.items()),
        )

    return spillovers


def propagate_all() -> Dict[str, Dict[str, float]]:
    """Propagate contagion from ALL active theaters above threshold.

    Called once per analysis cycle after updating the current
    theater's state.

    Steps:
        1. Decay stale contagion from previous cycles
        2. Iterate all theaters above SHOCK_THRESHOLD
        3. Propagate from each source

    Returns
    -------
    dict
        Mapping of source_country → {target_country → spillover}.
    """
    # Step 1: Decay stale contagion
    decay_contagion(CONTAGION_CYCLE_DECAY)

    # Step 2: Identify shock sources
    active = get_active_theaters(sre_threshold=SHOCK_THRESHOLD)

    if not active:
        logger.info("[CONTAGION] No theaters above threshold %.2f", SHOCK_THRESHOLD)
        return {}

    # Step 3: Propagate from each source
    all_spillovers: Dict[str, Dict[str, float]] = {}
    for cc in sorted(active.keys()):
        result = propagate_shock(cc)
        if result:
            all_spillovers[cc] = result

    total_affected = len({
        t for spills in all_spillovers.values() for t in spills
    })
    logger.info(
        "[CONTAGION] Propagated from %d sources → %d target theaters affected",
        len(all_spillovers), total_affected,
    )

    return all_spillovers


def contagion_summary() -> Dict[str, float]:
    """Return current contagion_received for all theaters (non-zero only)."""
    return {
        cc: t.contagion_received
        for cc, t in GLOBAL_THEATERS.items()
        if t.contagion_received > 0.001
    }
