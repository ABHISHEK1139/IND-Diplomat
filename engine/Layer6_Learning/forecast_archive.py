"""
Phase 6.1 — Forecast Archive
==============================

Persists every Phase-5 trajectory forecast to a JSON ledger so the
system can later compare predictions against reality.

Storage: ``data/forecast_history.json``  (append-only JSONL-style list)

Each entry records:
    - country, timestamp, session_id
    - prob_up (P(HIGH in 14 days)), prob_down, prob_stable
    - sre_escalation_score, velocity, ndi
    - expansion_mode
    - resolved (bool), brier_score (float|null)
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("Layer6_Learning.forecast_archive")

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_FORECAST_PATH = os.path.join(_DATA_DIR, "forecast_history.json")

_file_lock = threading.Lock()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Forecast Entry
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@dataclass
class ForecastEntry:
    """One recorded forecast."""
    country: str
    timestamp: str              # ISO-8601 UTC
    session_id: str
    prob_up: float              # P(HIGH in 14 days)
    prob_down: float
    prob_stable: float
    sre_escalation_score: float
    velocity: float
    ndi: float
    expansion_mode: str
    # ── Resolution fields (filled later) ──────────────────────
    resolved: bool = False
    resolution_timestamp: Optional[str] = None
    actual_outcome: Optional[int] = None   # 1 = HIGH occurred, 0 = did not
    brier_score: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ForecastEntry":
        # Accept only known fields
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Public API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def record_forecast(
    country: str,
    session_id: str,
    prob_up: float,
    prob_down: float,
    prob_stable: float,
    sre_escalation_score: float,
    velocity: float,
    ndi: float,
    expansion_mode: str,
) -> ForecastEntry:
    """Append a new forecast entry to the archive.

    Called once per analysis cycle, immediately after Phase-5
    trajectory computation completes.

    Returns the created ForecastEntry.
    """
    entry = ForecastEntry(
        country=country.upper().strip() or "UNKNOWN",
        timestamp=datetime.now(timezone.utc).isoformat(),
        session_id=str(session_id),
        prob_up=round(float(prob_up), 4),
        prob_down=round(float(prob_down), 4),
        prob_stable=round(float(prob_stable), 4),
        sre_escalation_score=round(float(sre_escalation_score), 4),
        velocity=round(float(velocity), 4),
        ndi=round(float(ndi), 4),
        expansion_mode=str(expansion_mode),
    )

    history = _load_raw()
    history.append(entry.to_dict())
    _save_raw(history)

    logger.info(
        "[FORECAST] Recorded: %s  P(HIGH)=%.1f%%  SRE=%.3f  vel=%.3f  NDI=%.3f",
        entry.country, entry.prob_up * 100, entry.sre_escalation_score,
        entry.velocity, entry.ndi,
    )
    return entry


def load_history(country: Optional[str] = None) -> List[ForecastEntry]:
    """Load forecast history, optionally filtered by country.

    Parameters
    ----------
    country : str or None
        If provided, return only entries matching this country code
        (case-insensitive).  If None, return all entries.
    """
    raw = _load_raw()
    entries = [ForecastEntry.from_dict(d) for d in raw]
    if country:
        cc = country.upper().strip()
        entries = [e for e in entries if e.country == cc]
    return entries


def save_history(entries: List[ForecastEntry]) -> None:
    """Overwrite the forecast history with updated entries.

    Used by forecast_resolution after marking entries as resolved.
    """
    _save_raw([e.to_dict() for e in entries])
    logger.info("[FORECAST] Saved %d entries to archive", len(entries))


def count_resolved(country: Optional[str] = None) -> int:
    """Count how many forecasts have been resolved."""
    return sum(1 for e in load_history(country) if e.resolved)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Internal I/O
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _load_raw() -> list:
    with _file_lock:
        if not os.path.exists(_FORECAST_PATH):
            return []
        try:
            with open(_FORECAST_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            logger.warning("[FORECAST] Corrupt archive — starting fresh")
            return []


def _save_raw(data: list) -> None:
    with _file_lock:
        os.makedirs(os.path.dirname(_FORECAST_PATH), exist_ok=True)
        with open(_FORECAST_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
