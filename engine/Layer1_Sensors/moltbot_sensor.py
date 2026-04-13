"""
Layer-1 MoltBot OSINT Sensor
==============================

Perception-mode sensor that sits alongside GDELT in the pipeline.
Called from ``state_provider.build_initial_state()`` BEFORE the council.

This is a thin wrapper around ``moltbot_adapter.run_batch_collection()``.
It exists so the state builder can import a clean function without
knowing about adapter internals.

Architecture position:
    WORLD_MONITOR
       ├── GDELT sweep          (structured events → observations)
       └── MoltBot sweep        (narrative articles → observations)  ← THIS
               ↓
    BELIEF ACCUMULATOR
               ↓
    STATE MODEL → COUNCIL → GATE

Design rules:
    - NEVER crash.  Always returns [].
    - No LLM.  Pure web fetch + regex extraction.
    - Cooldown: one sweep per country per 15 min (enforced in adapter).
    - Every observation is in the SAME format as GDELT so the
      BeliefAccumulator treats them identically.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("Layer1.sensors.moltbot_perception")


def collect_country_osint(country_code: str) -> List[Dict[str, Any]]:
    """
    Run a MoltBot OSINT sweep for a country and return observations.

    Equivalent to ``sense_gdelt(countries=[country_code])`` but for
    narrative news articles instead of structured event records.

    Parameters
    ----------
    country_code : str
        ISO 3-letter code (e.g. "IRN").

    Returns
    -------
    list[dict]
        Observation dicts in GDELT-compatible format.
        Empty list on any failure (sensor must never block pipeline).
    """
    try:
        from Core.intelligence.moltbot_adapter import run_batch_collection
        return run_batch_collection(country_code)
    except ImportError as e:
        logger.debug("[MOLTBOT-PERCEPTION] Import failed: %s", e)
        return []
    except Exception as e:
        logger.warning("[MOLTBOT-PERCEPTION] Sensor degraded: %s", e)
        return []
