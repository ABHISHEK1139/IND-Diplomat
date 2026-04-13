"""
State Engine — Snapshot history storage and trend computation.

Stores run snapshots in ``data/state_history/`` and computes
dimension trends as ``current − mean(last N runs)``.

This is a **non-destructive layer** — it does not modify the
temporal analysis or SRE core.  It reads from them and adds its
own historical perspective.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Layer4_Analysis.coordinator_modules.state_engine")

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "state_history")
_HISTORY_FILE = os.path.join(_DATA_DIR, "run_snapshots.json")
_file_lock = threading.Lock()


class StateSnapshotStore:
    """
    Stores and retrieves SRE dimension snapshots across runs.

    Each snapshot records:
    - timestamp
    - country
    - capability, intent, stability, cost
    - sre_score, risk_level
    """

    @staticmethod
    def save_snapshot(
        country: str,
        *,
        capability: float = 0.0,
        intent: float = 0.0,
        stability: float = 0.0,
        cost: float = 0.0,
        sre_score: float = 0.0,
        risk_level: str = "LOW",
        confidence: float = 0.0,
    ) -> Dict[str, Any]:
        """Save a new run snapshot."""
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "country": country.upper(),
            "capability": round(float(capability), 4),
            "intent": round(float(intent), 4),
            "stability": round(float(stability), 4),
            "cost": round(float(cost), 4),
            "sre_score": round(float(sre_score), 4),
            "risk_level": str(risk_level),
            "confidence": round(float(confidence), 4),
        }

        with _file_lock:
            os.makedirs(_DATA_DIR, exist_ok=True)
            history = StateSnapshotStore._load_all()
            history.append(snapshot)

            # Keep last 500 snapshots max
            if len(history) > 500:
                history = history[-500:]

            with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2)

        logger.info(
            "[STATE-SNAPSHOT] Saved: %s SRE=%.3f cap=%.3f int=%.3f stab=%.3f cost=%.3f",
            country, sre_score, capability, intent, stability, cost,
        )
        return snapshot

    @staticmethod
    def get_history(
        country: str,
        last_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get the last N snapshots for a country."""
        history = StateSnapshotStore._load_all()
        cc = country.upper()
        filtered = [s for s in history if s.get("country") == cc]
        return filtered[-last_n:]

    @staticmethod
    def _load_all() -> List[Dict[str, Any]]:
        """Load all snapshots from disk."""
        if not os.path.exists(_HISTORY_FILE):
            return []
        try:
            with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []


def compute_trend_from_snapshots(
    country: str,
    *,
    window: int = 3,
) -> Dict[str, float]:
    """
    Compute dimension trends as ``current − mean(last N runs)``.

    This is a **post-processing layer** — it does not replace
    the core temporal trend engine.  It adds multi-run trending.

    Parameters
    ----------
    country : str
        ISO-3 country code.
    window : int
        Number of past runs to average for comparison.

    Returns
    -------
    dict
        Keys: capability_trend, intent_trend, stability_trend,
        cost_trend, sre_trend.  Positive = increasing.
    """
    history = StateSnapshotStore.get_history(country, last_n=window + 1)

    if len(history) < 2:
        return {
            "capability_trend": 0.0,
            "intent_trend": 0.0,
            "stability_trend": 0.0,
            "cost_trend": 0.0,
            "sre_trend": 0.0,
        }

    current = history[-1]
    past = history[:-1]

    def avg(key: str) -> float:
        vals = [s.get(key, 0.0) for s in past]
        return sum(vals) / len(vals) if vals else 0.0

    return {
        "capability_trend": round(current.get("capability", 0) - avg("capability"), 4),
        "intent_trend": round(current.get("intent", 0) - avg("intent"), 4),
        "stability_trend": round(current.get("stability", 0) - avg("stability"), 4),
        "cost_trend": round(current.get("cost", 0) - avg("cost"), 4),
        "sre_trend": round(current.get("sre_score", 0) - avg("sre_score"), 4),
    }
