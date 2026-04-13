"""
Council Shadow Logger — Phase 1 Minister Shadow Mode
=====================================================
Appends one JSONL record per analysis session to
  data/council_shadow_log.jsonl
Each record captures:
  - timestamp, session_id, question
  - actual confidence (without council influence)
  - hypothetical confidence (with council influence)
  - council delta, adjustment, groupthink penalty
  - round1/round2 vote tallies
  - shadow_mode flag (True = ministers did NOT influence)

Usage from coordinator.py:
    from engine.Layer4_Analysis.council_shadow_log import log_council_shadow
    log_council_shadow(session, final_confidence, council_reasoning_dict)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Resolve log path relative to project data dir
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_LOG_PATH = os.path.join(_DATA_DIR, "council_shadow_log.jsonl")


def log_council_shadow(
    session: Any,
    final_confidence: float,
    council_reasoning: Dict[str, Any],
    question: str = "",
) -> None:
    """Append a single shadow-comparison record to the JSONL log.

    Parameters
    ----------
    session : CouncilSession
        The analysis session (used to pull session_id).
    final_confidence : float
        The actual confidence emitted by the pipeline.
    council_reasoning : dict
        The dict returned by _build_council_reasoning_dict().
    question : str
        The original analyst question / query.
    """
    try:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": str(getattr(session, "session_id", "") or ""),
            "question": question[:200],
            "shadow_mode": council_reasoning.get("shadow_mode", True),
            "final_confidence": round(final_confidence, 6),
            "conf_without_council": council_reasoning.get("conf_without_council", 0.0),
            "conf_with_council": council_reasoning.get("conf_with_council", 0.0),
            "council_delta": council_reasoning.get("council_delta", 0.0),
            "council_adjustment": council_reasoning.get("council_adjustment", 0.0),
            "groupthink_penalty": council_reasoning.get("groupthink_penalty", 0.0),
            "groupthink_flag": council_reasoning.get("groupthink_flag", False),
            "round1_votes": council_reasoning.get("round1_votes", {}),
            "round2_votes": council_reasoning.get("round2_votes", {}),
        }

        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

        logger.info("[COUNCIL-SHADOW-LOG] record written -> %s", _LOG_PATH)
    except Exception as exc:  # noqa: BLE001 — must never crash pipeline
        logger.warning("[COUNCIL-SHADOW-LOG] write failed: %s", exc)
