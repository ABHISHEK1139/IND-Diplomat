"""
Layer 3: Temporal Memory
========================
Tracks the evolution of beliefs over time.
"""

import json
import logging
import os
import statistics
from typing import List, Dict, Optional
from datetime import datetime, timezone
from dip.core.schema import Belief, TemporalIndicator
from dip.core.fuzzy import rising

logger = logging.getLogger("Layer3.temporal_memory")

_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "state_history", "belief_history.jsonl")

MIN_HISTORY_REQUIRED = 4
TREND_WINDOW = 10
SPIKE_SIGMA = 2.0


def record_snapshot(beliefs: List[Belief]):
    """Records the current beliefs as a snapshot."""
    os.makedirs(os.path.dirname(_HISTORY_FILE), exist_ok=True)
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "beliefs": {b.signal_code: b.support_score for b in beliefs}
    }
    try:
        with open(_HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot) + "\n")
    except Exception as e:
        logger.error(f"Failed to record snapshot: {e}")


def _load_history() -> List[Dict]:
    if not os.path.exists(_HISTORY_FILE):
        return []
    history = []
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    history.append(json.loads(line))
    except Exception as e:
        logger.error(f"Failed to load history: {e}")
    return history[-TREND_WINDOW:]


def compute_trends(signal_code: str, current_score: float) -> TemporalIndicator:
    history = _load_history()
    scores = [h.get("beliefs", {}).get(signal_code, 0.0) for h in history]
    scores.append(current_score)

    indicator = TemporalIndicator(signal=signal_code)

    if len(scores) < MIN_HISTORY_REQUIRED:
        return indicator

    # Momentum (Linear regression slope)
    n = len(scores)
    x_mean = (n - 1) / 2
    y_mean = sum(scores) / n
    numerator = sum((i - x_mean) * (scores[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    momentum = numerator / denominator if denominator != 0 else 0.0
    indicator.momentum = round(momentum, 4)

    # Persistence
    persistence_count = sum(1 for s in scores[-5:] if s > 0.30)
    indicator.persistence = round(persistence_count / 5.0, 4)

    # Spike detection
    past_scores = scores[:-1]
    mean = statistics.mean(past_scores)
    std_dev = statistics.stdev(past_scores) if len(past_scores) > 1 else 0.0
    if std_dev > 0 and current_score > (mean + SPIKE_SIGMA * std_dev):
        indicator.is_spike = True
        indicator.spike_severity = round((current_score - mean) / std_dev, 2)

    # Trend label via fuzzy logic
    is_rising = rising(momentum, 0.0, 0.15)
    if is_rising > 0.5:
        indicator.trend_label = "accelerating"
    elif momentum < -0.05:
        indicator.trend_label = "decelerating"
    else:
        indicator.trend_label = "stable"

    return indicator
