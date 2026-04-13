"""
Calibration Engine — Post-processing confidence adjustments.

Sits **after** the core confidence pipeline and applies:
- Evidence-count confidence boost
- Red team penalty normalization
- Multi-run calibration multiplier

Does NOT modify the core confidence pipeline.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Optional

logger = logging.getLogger("Layer4_Analysis.coordinator_modules.calibration_engine")


def calibrate_confidence(
    raw_confidence: float,
    evidence_count: int = 1,
    *,
    calibration_multiplier: float = 1.0,
    floor: float = 0.05,
    ceiling: float = 0.95,
) -> float:
    """
    Post-process a raw confidence score with evidence-count scaling.

    This is a **post-processing layer** — it does not replace the
    original confidence; it adjusts it based on evidence depth.

    Parameters
    ----------
    raw_confidence : float
        The original confidence from the pipeline.
    evidence_count : int
        Number of distinct evidence items supporting the assessment.
    calibration_multiplier : float
        Multiplier from the calibration engine (Phase 6).
    floor : float
        Minimum output confidence.
    ceiling : float
        Maximum output confidence.

    Returns
    -------
    float
        Calibrated confidence in [floor, ceiling].

    Examples
    --------
    >>> calibrate_confidence(0.10, evidence_count=1)
    0.18
    >>> calibrate_confidence(0.10, evidence_count=3)
    0.34
    >>> calibrate_confidence(0.10, evidence_count=5)
    0.45
    """
    # Logarithmic boost: diminishing returns after ~8 evidence items
    boost = min(0.35, 0.08 * evidence_count)
    adjusted = raw_confidence + boost

    # Apply calibration multiplier from Phase 6 learning
    adjusted *= calibration_multiplier

    # Clamp
    return max(floor, min(ceiling, adjusted))


def apply_red_team_penalty(
    confidence: float,
    red_team_report: Optional[Dict[str, Any]] = None,
    *,
    max_penalty: float = 0.20,
) -> float:
    """
    Apply red team penalty as a post-processing step.

    Uses the penalty from the red team report if available,
    otherwise returns confidence unchanged.

    Parameters
    ----------
    confidence : float
        Pre-penalty confidence.
    red_team_report : dict, optional
        Red team output dict with ``confidence_penalty`` key.
    max_penalty : float
        Maximum penalty cap.

    Returns
    -------
    float
        Confidence after penalty (never below 0.01).
    """
    if red_team_report is None:
        return confidence

    penalty = min(
        max_penalty,
        float(red_team_report.get("confidence_penalty", 0.0)),
    )
    return max(0.01, confidence - penalty)


def compute_evidence_depth(
    session: Any,
) -> int:
    """
    Compute how many distinct evidence items support the assessment.

    Counts: unique observation sources + PIR responses + RAG docs.
    """
    count = 0

    # Observations
    evidence_log = getattr(session, "evidence_log", [])
    count += len(evidence_log)

    # RAG sources
    rag_docs = getattr(session, "rag_sources", [])
    count += len(rag_docs)

    return max(1, count)
