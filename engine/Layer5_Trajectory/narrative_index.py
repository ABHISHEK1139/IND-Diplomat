"""
Layer5_Trajectory — Narrative Drift Index (NDI)
================================================

Computes the Narrative Drift Index from GKG metrics and Goldstein
severity data.  NDI measures how rapidly the media/diplomatic
narrative is shifting toward hostility.

NDI = 0.4 × theme_velocity + 0.3 × severity_index + 0.3 × negative_tone_shift

Phase 5 ONLY.  Never touches SRE core.

Uses CAMEO Goldstein scale from cameo_config (already loaded by
the GDELT sensor).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger("Layer5_Trajectory.narrative_index")

# ── Goldstein lookup (imported from cameo_config) ─────────────────────
try:
    from engine.Layer1_Collection.sensors.cameo_config import (
        CAMEO_GOLDSTEIN as _CAMEO_GOLDSTEIN,
    )
except (ImportError, ModuleNotFoundError):
    _CAMEO_GOLDSTEIN: dict = {}

# ── NDI weights ───────────────────────────────────────────────────────
W_THEME_VELOCITY    = 0.40
W_SEVERITY_INDEX    = 0.30
W_NEGATIVE_TONE     = 0.30

# ── Stability guard: cap NDI contribution ─────────────────────────────
NDI_MAX = 1.0

# ── Theme velocity baseline (how many themes = "normal") ─────────────
THEME_VELOCITY_NORMALIZER = 100  # 100 matching themes = velocity 1.0


@dataclass
class NarrativeDriftResult:
    """Result of NDI computation."""
    ndi: float = 0.0
    theme_velocity: float = 0.0
    severity_index: float = 0.0
    negative_tone_shift: float = 0.0
    goldstein_avg: float = 0.0
    valid: bool = False

    def to_dict(self) -> dict:
        return {
            "ndi": round(self.ndi, 4),
            "theme_velocity": round(self.theme_velocity, 4),
            "severity_index": round(self.severity_index, 4),
            "negative_tone_shift": round(self.negative_tone_shift, 4),
            "goldstein_avg": round(self.goldstein_avg, 4),
            "valid": self.valid,
        }


def compute_severity_from_goldstein(
    event_codes: Optional[List[str]] = None,
    goldstein_scores: Optional[List[float]] = None,
) -> float:
    """
    Compute narrative severity index from Goldstein scores.

    Uses either raw Goldstein scores or CAMEO event codes mapped
    via the lookup table.

    Returns severity_index in [0.0, 1.0]:
        avg(|negative_goldstein_scores|) / 10.0
    """
    scores: List[float] = []

    # Use provided raw scores
    if goldstein_scores:
        scores.extend(goldstein_scores)

    # Map event codes to Goldstein values via lookup
    if event_codes and _CAMEO_GOLDSTEIN:
        for code in event_codes:
            g = _CAMEO_GOLDSTEIN.get(str(code).strip())
            if g is not None:
                scores.append(float(g))

    if not scores:
        return 0.0

    # Only consider negative scores (hostile/conflictual)
    negative = [abs(s) for s in scores if s < 0]
    if not negative:
        return 0.0

    avg_neg = sum(negative) / len(negative)
    # Normalize: max Goldstein magnitude is 10.0
    severity = min(1.0, avg_neg / 10.0)
    return severity


def compute_narrative_drift(
    gkg_metrics,
    previous_ndi: float = 0.0,
) -> NarrativeDriftResult:
    """
    Compute the Narrative Drift Index from GKG aggregate metrics.

    Parameters
    ----------
    gkg_metrics : NarrativeMetrics
        Output from gkg_ingest.fetch_and_parse_gkg().
    previous_ndi : float
        Previous run's NDI for delta computation (currently unused,
        reserved for 7-day rolling window).

    Returns
    -------
    NarrativeDriftResult
    """
    result = NarrativeDriftResult()

    if gkg_metrics is None:
        return result

    total = getattr(gkg_metrics, "total_articles", 0)
    theme_counts = getattr(gkg_metrics, "theme_counts", {}) or {}
    avg_tone = getattr(gkg_metrics, "avg_tone", 0.0)
    neg_ratio = getattr(gkg_metrics, "negative_tone_ratio", 0.0)
    valid = getattr(gkg_metrics, "valid", False)
    event_codes = getattr(gkg_metrics, "event_codes", []) or []
    goldstein_scores = getattr(gkg_metrics, "goldstein_scores", []) or []

    # ── Theme velocity ───────────────────────────────────────────
    # How many matching themes appeared, normalized.
    total_theme_hits = sum(theme_counts.values()) if theme_counts else 0
    theme_velocity = min(1.0, total_theme_hits / THEME_VELOCITY_NORMALIZER)

    # ── Severity index from Goldstein scale ──────────────────────
    severity_index = compute_severity_from_goldstein(event_codes, goldstein_scores)

    # ── Negative tone shift ──────────────────────────────────────
    # Combine avg_tone negativity and negative article ratio.
    # avg_tone ranges roughly from -10 to +10; normalize.
    tone_negativity = max(0.0, min(1.0, -avg_tone / 5.0)) if avg_tone < 0 else 0.0
    negative_tone_shift = min(1.0, 0.6 * neg_ratio + 0.4 * tone_negativity)

    # ── Composite NDI ────────────────────────────────────────────
    ndi = (
        W_THEME_VELOCITY * theme_velocity
        + W_SEVERITY_INDEX * severity_index
        + W_NEGATIVE_TONE * negative_tone_shift
    )
    ndi = max(0.0, min(NDI_MAX, ndi))

    result.ndi = ndi
    result.theme_velocity = theme_velocity
    result.severity_index = severity_index
    result.negative_tone_shift = negative_tone_shift
    result.goldstein_avg = (
        sum(goldstein_scores) / len(goldstein_scores) if goldstein_scores else 0.0
    )
    result.valid = valid

    logger.info(
        "[NDI] theme_vel=%.3f  severity=%.3f  neg_tone=%.3f  → NDI=%.3f (valid=%s)",
        theme_velocity, severity_index, negative_tone_shift, ndi, valid,
    )

    return result
