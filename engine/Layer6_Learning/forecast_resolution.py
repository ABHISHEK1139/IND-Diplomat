"""
Phase 6.2 — Forecast Resolution
=================================

After 14 days, check whether HIGH actually occurred for each
unresolved forecast.  Compute Brier score per entry.

Definition of "HIGH occurred":
    The country's SRE escalation score crossed > 0.60 in any
    subsequent analysis cycle within the resolution window.

Brier Score:
    ``(forecast_probability - actual_outcome) ** 2``
    where actual = 1 if HIGH occurred, 0 otherwise.

    Perfect: 0.00   Random: 0.25   Worst: 1.00
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from engine.Layer6_Learning.forecast_archive import (
    ForecastEntry,
    load_history,
    save_history,
)

logger = logging.getLogger("Layer6_Learning.forecast_resolution")

# ── Resolution window ────────────────────────────────────────────
RESOLUTION_WINDOW_DAYS = 14
HIGH_THRESHOLD = 0.60     # escalation_score > this → HIGH occurred


def resolve_forecasts(
    current_escalation_by_country: Dict[str, float],
) -> Dict[str, any]:
    """Attempt to resolve all unresolved forecasts.

    Parameters
    ----------
    current_escalation_by_country : dict
        Mapping of country code → current SRE escalation score.
        The coordinator passes ``{country: sre_esc}`` on each run.

    Returns
    -------
    dict
        ``{"newly_resolved": int, "total_resolved": int,
           "total_unresolved": int, "avg_brier": float|None}``
    """
    entries = load_history()
    if not entries:
        return _summary(entries, 0)

    now = datetime.now(timezone.utc)
    newly_resolved = 0

    for entry in entries:
        if entry.resolved:
            continue

        # Check expiry
        try:
            forecast_time = datetime.fromisoformat(entry.timestamp)
        except (ValueError, TypeError):
            continue

        elapsed = (now - forecast_time).total_seconds() / 86400.0

        # ── Still inside window: check live escalation ────────
        cc = entry.country.upper()
        current_esc = current_escalation_by_country.get(cc, None)

        if current_esc is not None and current_esc > HIGH_THRESHOLD:
            # HIGH occurred — resolve immediately
            entry.resolved = True
            entry.actual_outcome = 1
            entry.brier_score = round((entry.prob_up - 1.0) ** 2, 6)
            entry.resolution_timestamp = now.isoformat()
            newly_resolved += 1
            logger.info(
                "[RESOLVE] %s HIGH occurred (esc=%.3f) — Brier=%.4f",
                cc, current_esc, entry.brier_score,
            )
            continue

        # ── Window expired without HIGH ───────────────────────
        if elapsed >= RESOLUTION_WINDOW_DAYS:
            entry.resolved = True
            entry.actual_outcome = 0
            entry.brier_score = round((entry.prob_up - 0.0) ** 2, 6)
            entry.resolution_timestamp = now.isoformat()
            newly_resolved += 1
            logger.info(
                "[RESOLVE] %s window expired (%.0f days) — no HIGH — Brier=%.4f",
                cc, elapsed, entry.brier_score,
            )

    if newly_resolved > 0:
        save_history(entries)

    return _summary(entries, newly_resolved)


def resolve_single_country(
    country: str,
    current_escalation: float,
) -> Dict[str, any]:
    """Resolve forecasts for a single country.

    Convenience wrapper around ``resolve_forecasts``.
    """
    return resolve_forecasts({country.upper(): current_escalation})


def resolve_pending() -> Dict[str, any]:
    """Phase 8: Background resolver — resolve all expired forecasts.

    Called at pipeline start to resolve any forecast whose 14-day window
    has elapsed without a new run triggering live resolution.  This
    ensures the calibration engine eventually accumulates resolved
    entries even when the system isn't run daily.

    Forecasts inside the window are left unresolved (they need a live
    SRE check to know whether HIGH occurred).
    """
    entries = load_history()
    if not entries:
        return _summary(entries, 0)

    now = datetime.now(timezone.utc)
    newly_resolved = 0

    for entry in entries:
        if entry.resolved:
            continue

        try:
            forecast_time = datetime.fromisoformat(entry.timestamp)
        except (ValueError, TypeError):
            continue

        elapsed = (now - forecast_time).total_seconds() / 86400.0

        # Only resolve expired windows — live checks need current SRE
        if elapsed >= RESOLUTION_WINDOW_DAYS:
            entry.resolved = True
            entry.actual_outcome = 0
            entry.brier_score = round((entry.prob_up - 0.0) ** 2, 6)
            entry.resolution_timestamp = now.isoformat()
            newly_resolved += 1
            logger.info(
                "[RESOLVE-PENDING] %s window expired (%.0f days) — "
                "no HIGH — Brier=%.4f",
                entry.country, elapsed, entry.brier_score,
            )

    if newly_resolved > 0:
        save_history(entries)
        logger.info(
            "[RESOLVE-PENDING] Resolved %d expired forecasts", newly_resolved,
        )

    return _summary(entries, newly_resolved)


def get_resolved_entries(country: Optional[str] = None) -> List[ForecastEntry]:
    """Return only resolved forecast entries."""
    return [e for e in load_history(country) if e.resolved]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _summary(entries: List[ForecastEntry], newly: int) -> dict:
    resolved = [e for e in entries if e.resolved]
    unresolved = [e for e in entries if not e.resolved]
    briers = [e.brier_score for e in resolved if e.brier_score is not None]
    avg_brier = round(sum(briers) / len(briers), 6) if briers else None
    return {
        "newly_resolved": newly,
        "total_resolved": len(resolved),
        "total_unresolved": len(unresolved),
        "total_forecasts": len(entries),
        "avg_brier": avg_brier,
    }
