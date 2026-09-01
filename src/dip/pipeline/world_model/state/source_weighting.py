"""
Dynamic Source Reliability — PyMC Bayesian Updating
=====================================================

Replaces flat reliability lookup with Beta-distribution Bayesian updating.
Each source is modeled as Beta(α=successes+1, β=failures+1).

Port of DIP_8 source_weighting.py enhanced with Autonomous_3.0 patterns.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger("Layer3_State.source_weighting")

try:
    import pymc as pm
    PYMC_AVAILABLE = True
except ImportError:
    PYMC_AVAILABLE = False
    logger.info("PyMC not installed. Using Beta conjugate update fallback.")


RELIABILITY_PATH = Path(__file__).resolve().parent.parent / "data" / "source_reliability.json"

# Default reliability priors (Beta distribution parameters)
DEFAULT_PRIORS: Dict[str, Tuple[float, float]] = {
    "SOCIAL": (3, 7),
    "OSINT": (5, 5),
    "NEWS": (6, 4),
    "REUTERS": (7, 3),
    "BBC": (7, 3),
    "GOV": (8, 2),
    "UN": (8, 2),
    "SIPRI": (9, 1),
    "SENSOR": (9, 1),
    "SATELLITE": (9, 1),
    "SIGINT": (8, 2),
    "HUMINT": (7, 3),
    "ANALYST": (7, 3),
    "DATASET": (9, 1),
}


class SourceReliability:
    """Bayesian source reliability tracker."""

    def __init__(self):
        # Beta params: {source_type: [alpha, beta]}
        self.params: Dict[str, List[float]] = {}
        self.history: List[Dict[str, Any]] = []
        for st, (a, b) in DEFAULT_PRIORS.items():
            self.params[st] = [float(a), float(b)]
        self._load()

    def _load(self) -> None:
        if RELIABILITY_PATH.exists():
            try:
                with open(RELIABILITY_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.params = data.get("params", self.params)
                self.history = data.get("history", [])
            except Exception:
                pass

    def _save(self) -> None:
        RELIABILITY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RELIABILITY_PATH, "w", encoding="utf-8") as f:
            json.dump({"params": self.params, "history": self.history[-1000:]}, f, indent=2)

    def get_reliability(self, source_type: str) -> float:
        """Get current reliability estimate (mean of Beta distribution)."""
        a, b = self.params.get(source_type.upper(), (5, 5))
        return round(a / (a + b), 4) if (a + b) > 0 else 0.5

    def update(self, source_type: str, verified: bool) -> float:
        """Update source reliability with a verification outcome.
        
        verified=True → Beta(α+1, β)
        verified=False → Beta(α, β+1)
        """
        st = source_type.upper()
        if st not in self.params:
            self.params[st] = [5.0, 5.0]

        a, b = self.params[st]
        if verified:
            a += 1.0
        else:
            b += 1.0
        self.params[st] = [a, b]

        reliability = round(a / (a + b), 4)
        self.history.append({
            "source_type": st,
            "verified": verified,
            "new_alpha": a,
            "new_beta": b,
            "reliability": reliability,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save()
        return reliability

    def detect_degradation(self, source_type: str, window: int = 20) -> Optional[Dict[str, Any]]:
        """Detect if a source is degrading (reliability trending down)."""
        recent = [h for h in self.history[-window:] if h["source_type"] == source_type.upper()]
        if len(recent) < 5:
            return None

        reliabilities = [h["reliability"] for h in recent]
        slope = np.polyfit(range(len(reliabilities)), reliabilities, 1)[0]

        if slope < -0.01:  # declining
            return {
                "source_type": source_type,
                "trend": "degrading",
                "slope": round(slope, 4),
                "current_reliability": reliabilities[-1],
                "reliability_7d_ago": reliabilities[0] if len(reliabilities) >= 7 else reliabilities[0],
                "alert": f"Source {source_type} reliability declining ({slope:.4f}/update). Review source.",
            }
        return None

    def get_all_reliabilities(self) -> Dict[str, Dict[str, Any]]:
        """Get reliability for all tracked sources."""
        return {
            st: {
                "alpha": self.params[st][0],
                "beta": self.params[st][1],
                "reliability": round(self.params[st][0] / (sum(self.params[st])), 4),
                "observations": int(sum(self.params[st]) - sum(DEFAULT_PRIORS.get(st, (5, 5)))),
            }
            for st in sorted(self.params.keys())
        }


_source_reliability: Optional[SourceReliability] = None


def get_source_reliability() -> SourceReliability:
    global _source_reliability
    if _source_reliability is None:
        _source_reliability = SourceReliability()
    return _source_reliability
