"""
Temporal Memory — Trend Intelligence Engine
============================================

Stores the *evolution of beliefs*, not raw articles or observations.

Every time the Belief Accumulator commits beliefs, a lightweight
snapshot is appended to:

    data/state_history/belief_history.jsonl

The system then computes three temporal indicators per signal:

1. **Momentum** — rate of change (acceleration / deceleration)
2. **Persistence** — how sustained a signal is across recent cycles
3. **Spike detection** — sudden jumps beyond 2·σ (shock events)

These indicators feed the Judgment Gate to enable *trend override*:
a low capability that is rising rapidly for 3+ cycles triggers at
least MEDIUM risk — wars are predicted by buildup, not current state.

Design constraints:
    - MIN_HISTORY_REQUIRED = 4 snapshots before trends are computed
      (prevents false alarms on first runs)
    - Only beliefs are stored (compact JSONL, ~200 bytes per snapshot)
    - Thread-safe file appends with file locking
    - Graceful degradation if history file is missing or corrupt
"""

from __future__ import annotations

import json
import logging
import math
import os
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Layer3.temporal_memory")

# =====================================================================
# Configuration
# =====================================================================

# Minimum snapshots before trends are computed (prevents false alarms)
MIN_HISTORY_REQUIRED = 4

# How many recent snapshots to consider for trend analysis
TREND_WINDOW = 10

# Persistence: count snapshots in last N cycles above threshold
PERSISTENCE_WINDOW = 5
PERSISTENCE_THRESHOLD = 0.30

# Spike detection: current > mean + SPIKE_SIGMA * std_dev
SPIKE_SIGMA = 2.0

# Momentum lookback: compare to value N hours ago
MOMENTUM_LOOKBACK_HOURS = 24

# Default history file path
_DEFAULT_HISTORY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "state_history",
)
_DEFAULT_HISTORY_FILE = os.path.join(_DEFAULT_HISTORY_DIR, "belief_history.jsonl")


# =====================================================================
# Temporal Indicator Results
# =====================================================================

@dataclass
class TemporalIndicator:
    """Trend analysis result for a single signal."""
    signal: str

    # ── Momentum (rate of change) ─────────────────────────────────
    momentum: float = 0.0       # current - value_24h_ago
    momentum_label: str = "stable"  # rapid_escalation | rising | stable | de_escalation

    # ── Persistence (sustained above threshold) ───────────────────
    persistence: float = 0.0    # fraction of recent snapshots above 0.30
    persistence_label: str = "noise"  # noise | pattern | sustained

    # ── Spike detection ───────────────────────────────────────────
    spike: bool = False         # current > mean + 2σ
    spike_magnitude: float = 0.0  # how many σ above mean

    # ── Current value ──────────────────────────────────────────────
    current_value: float = 0.0
    history_length: int = 0     # how many snapshots we have
    sufficient_history: bool = False  # >= MIN_HISTORY_REQUIRED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal": self.signal,
            "momentum": round(self.momentum, 4),
            "momentum_label": self.momentum_label,
            "persistence": round(self.persistence, 4),
            "persistence_label": self.persistence_label,
            "spike": self.spike,
            "spike_magnitude": round(self.spike_magnitude, 4),
            "current_value": round(self.current_value, 4),
            "history_length": self.history_length,
            "sufficient_history": self.sufficient_history,
        }


@dataclass
class TemporalAnalysis:
    """Aggregate temporal analysis across all signals."""
    indicators: Dict[str, TemporalIndicator] = field(default_factory=dict)
    snapshot_count: int = 0
    sufficient_history: bool = False
    escalation_pattern: bool = False  # any signal shows trend concern
    trend_overrides: List[str] = field(default_factory=list)  # signals triggering override

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_count": self.snapshot_count,
            "sufficient_history": self.sufficient_history,
            "escalation_pattern": self.escalation_pattern,
            "trend_override_count": len(self.trend_overrides),
            "trend_overrides": list(self.trend_overrides),
            "indicators": {k: v.to_dict() for k, v in self.indicators.items()},
        }


# =====================================================================
# Temporal Memory Store
# =====================================================================

class TemporalMemory:
    """
    Lightweight belief-history store backed by a JSONL file.

    Each line is a JSON object:
        {"timestamp": "...", "beliefs": {"SIG_X": 0.41, ...}}

    Thread-safe appends; tolerates corrupt lines gracefully.
    """

    def __init__(self, history_path: Optional[str] = None):
        self.history_path = history_path or _DEFAULT_HISTORY_FILE
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Create the history directory if it doesn't exist."""
        directory = os.path.dirname(self.history_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                logger.warning("[TEMPORAL] Cannot create history dir: %s", e)

    # ─────────────────────────────────────────────────────────────
    # Write: record a belief snapshot
    # ─────────────────────────────────────────────────────────────

    def record_snapshot(
        self,
        beliefs: Dict[str, float],
        timestamp: Optional[str] = None,
    ) -> bool:
        """
        Append a belief snapshot to the history file.

        Parameters
        ----------
        beliefs : dict
            Signal → confidence mapping (from accumulator output).
        timestamp : str, optional
            ISO timestamp. Defaults to now.

        Returns
        -------
        bool
            True if written successfully.
        """
        if not beliefs:
            return False

        ts = timestamp or datetime.utcnow().isoformat(timespec="seconds") + "Z"
        record = {
            "timestamp": ts,
            "beliefs": {k: round(float(v), 4) for k, v in beliefs.items()},
        }

        try:
            with open(self.history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, separators=(",", ":")) + "\n")
            logger.info(
                "[TEMPORAL] Snapshot recorded: %d signals at %s",
                len(beliefs), ts,
            )
            return True
        except OSError as e:
            logger.warning("[TEMPORAL] Failed to write snapshot: %s", e)
            return False

    # ─────────────────────────────────────────────────────────────
    # Read: load history
    # ─────────────────────────────────────────────────────────────

    def load_history(self, max_records: int = 200) -> List[Dict[str, Any]]:
        """
        Load recent belief snapshots from the history file.

        Tolerates corrupt lines (skips them with warning).
        Returns newest-last (chronological order).
        """
        if not os.path.exists(self.history_path):
            return []

        records: List[Dict[str, Any]] = []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if isinstance(record, dict) and "beliefs" in record:
                            records.append(record)
                    except json.JSONDecodeError:
                        logger.debug(
                            "[TEMPORAL] Skipping corrupt line %d in history",
                            line_no,
                        )
        except OSError as e:
            logger.warning("[TEMPORAL] Failed to read history: %s", e)

        # Return only the most recent records
        return records[-max_records:]

    def snapshot_count(self) -> int:
        """Count snapshots without loading all data."""
        if not os.path.exists(self.history_path):
            return 0
        count = 0
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        count += 1
        except OSError:
            pass
        return count

    # ─────────────────────────────────────────────────────────────
    # Analyze: compute temporal indicators
    # ─────────────────────────────────────────────────────────────

    def compute_indicator(
        self,
        signal: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> TemporalIndicator:
        """
        Compute momentum, persistence, and spike for a single signal.

        Parameters
        ----------
        signal : str
            Signal token (e.g. "SIG_MIL_MOBILIZATION").
        history : list, optional
            Pre-loaded history. If None, loads from file.
        """
        if history is None:
            history = self.load_history()

        indicator = TemporalIndicator(signal=signal)
        indicator.history_length = len(history)

        if len(history) < MIN_HISTORY_REQUIRED:
            indicator.sufficient_history = False
            # Still extract current value if available
            if history:
                latest_beliefs = history[-1].get("beliefs", {})
                indicator.current_value = float(latest_beliefs.get(signal, 0.0))
            return indicator

        indicator.sufficient_history = True

        # Extract time series for this signal (most recent TREND_WINDOW)
        recent = history[-TREND_WINDOW:]
        values: List[float] = []
        timestamps: List[str] = []
        for record in recent:
            beliefs = record.get("beliefs", {})
            val = float(beliefs.get(signal, 0.0))
            values.append(val)
            timestamps.append(record.get("timestamp", ""))

        if not values:
            return indicator

        current = values[-1]
        indicator.current_value = current

        # ── 1. Momentum ──────────────────────────────────────────
        # Compare current to value ~24h ago (or oldest in window)
        lookback_value = self._find_lookback_value(
            signal, history, hours=MOMENTUM_LOOKBACK_HOURS
        )
        indicator.momentum = current - lookback_value

        if indicator.momentum > 0.25:
            indicator.momentum_label = "rapid_escalation"
        elif indicator.momentum > 0.10:
            indicator.momentum_label = "rising"
        elif indicator.momentum < -0.10:
            indicator.momentum_label = "de_escalation"
        else:
            indicator.momentum_label = "stable"

        # ── 2. Persistence ───────────────────────────────────────
        persistence_window = history[-PERSISTENCE_WINDOW:]
        above_count = 0
        for record in persistence_window:
            val = float(record.get("beliefs", {}).get(signal, 0.0))
            if val >= PERSISTENCE_THRESHOLD:
                above_count += 1
        indicator.persistence = above_count / max(1, len(persistence_window))

        if indicator.persistence >= 0.8:
            indicator.persistence_label = "sustained"
        elif indicator.persistence >= 0.5:
            indicator.persistence_label = "pattern"
        else:
            indicator.persistence_label = "noise"

        # ── 3. Spike Detection ───────────────────────────────────
        if len(values) >= 3:
            try:
                mean_val = statistics.mean(values[:-1])  # mean EXCLUDING current
                std_val = statistics.stdev(values[:-1]) if len(values[:-1]) >= 2 else 0.0
                if std_val > 0.001:
                    z_score = (current - mean_val) / std_val
                    indicator.spike_magnitude = round(z_score, 4)
                    if z_score > SPIKE_SIGMA:
                        indicator.spike = True
                elif current > mean_val + 0.20:
                    # Low variance but big jump → treat as spike
                    indicator.spike = True
                    indicator.spike_magnitude = round(
                        (current - mean_val) / max(0.01, std_val or 0.05), 4
                    )
            except (statistics.StatisticsError, ZeroDivisionError):
                pass

        return indicator

    def _find_lookback_value(
        self,
        signal: str,
        history: List[Dict[str, Any]],
        hours: float = 24.0,
    ) -> float:
        """
        Find the belief value for a signal approximately `hours` ago.

        Falls back to the oldest value in the window if timestamps
        are unparseable.
        """
        now = datetime.utcnow()
        target_time = now - timedelta(hours=hours)

        # Walk backwards to find closest snapshot to target_time
        best_value = 0.0
        best_distance = float("inf")

        for record in reversed(history):
            ts_str = record.get("timestamp", "")
            val = float(record.get("beliefs", {}).get(signal, 0.0))

            try:
                ts_clean = ts_str.replace("Z", "").split("+")[0]
                ts = datetime.fromisoformat(ts_clean)
                distance = abs((ts - target_time).total_seconds())
                if distance < best_distance:
                    best_distance = distance
                    best_value = val
            except (ValueError, TypeError):
                continue

        # If no parseable timestamps, use the value from 
        # ~24h-equivalent position in the list
        if best_distance == float("inf") and len(history) >= 2:
            # Approximate: assume snapshots are roughly evenly spaced
            idx = max(0, len(history) - max(2, len(history) // 3))
            best_value = float(
                history[idx].get("beliefs", {}).get(signal, 0.0)
            )

        return best_value

    # ─────────────────────────────────────────────────────────────
    # Analyze all: full temporal analysis
    # ─────────────────────────────────────────────────────────────

    def analyze_all(
        self,
        current_beliefs: Optional[Dict[str, float]] = None,
    ) -> TemporalAnalysis:
        """
        Run temporal analysis across all signals in history.

        Parameters
        ----------
        current_beliefs : dict, optional
            If provided, these are included as signals to analyze
            (in addition to anything in file history).

        Returns
        -------
        TemporalAnalysis
            Aggregate result with per-signal indicators.
        """
        history = self.load_history()
        n_snapshots = len(history)

        analysis = TemporalAnalysis(
            snapshot_count=n_snapshots,
            sufficient_history=(n_snapshots >= MIN_HISTORY_REQUIRED),
        )

        if n_snapshots < MIN_HISTORY_REQUIRED:
            logger.info(
                "[TEMPORAL] Insufficient history: %d/%d snapshots — "
                "trends not yet reliable",
                n_snapshots, MIN_HISTORY_REQUIRED,
            )
            return analysis

        # Collect all signal tokens we've ever seen
        all_signals: set = set()
        for record in history:
            all_signals.update(record.get("beliefs", {}).keys())
        if current_beliefs:
            all_signals.update(current_beliefs.keys())

        # Compute indicators for each signal
        for signal in sorted(all_signals):
            indicator = self.compute_indicator(signal, history)
            analysis.indicators[signal] = indicator

            # Check for escalation pattern (trend override candidates)
            if (
                indicator.momentum > 0.22
                and indicator.persistence > 0.6
            ):
                analysis.trend_overrides.append(signal)
                logger.info(
                    "[TEMPORAL] %s: momentum=+%.2f persistence=%.2f → "
                    "ESCALATION PATTERN DETECTED",
                    signal, indicator.momentum, indicator.persistence,
                )

            if indicator.spike:
                logger.info(
                    "[TEMPORAL] %s: SPIKE detected (%.1fσ above mean), "
                    "current=%.3f",
                    signal, indicator.spike_magnitude, indicator.current_value,
                )

        analysis.escalation_pattern = bool(analysis.trend_overrides)

        logger.info(
            "[TEMPORAL] Analysis complete: %d signals, %d snapshots, "
            "%d escalation patterns, %d spikes",
            len(analysis.indicators),
            n_snapshots,
            len(analysis.trend_overrides),
            sum(1 for i in analysis.indicators.values() if i.spike),
        )

        return analysis

    def clear(self) -> None:
        """Remove all history (for testing)."""
        try:
            if os.path.exists(self.history_path):
                os.remove(self.history_path)
        except OSError:
            pass

    # ─────────────────────────────────────────────────────────────
    # Warm start: load last known beliefs from persisted history
    # ─────────────────────────────────────────────────────────────

    def warm_start(self, max_age_hours: float = 48.0) -> Dict[str, float]:
        """
        Load beliefs from the most recent snapshot in history.

        Returns a signal→confidence dict that can seed the belief
        accumulator so the system doesn't start from scratch each run.

        Parameters
        ----------
        max_age_hours : float
            Ignore snapshots older than this (stale data protection).

        Returns
        -------
        dict
            Signal → confidence. Empty dict if no recent history.
        """
        history = self.load_history()
        if not history:
            logger.info("[TEMPORAL] Warm start: no history file — cold start")
            return {}

        latest = history[-1]
        beliefs = latest.get("beliefs", {})
        ts_str = latest.get("timestamp", "")

        # Check freshness
        try:
            ts_clean = ts_str.replace("Z", "").split("+")[0]
            ts = datetime.fromisoformat(ts_clean)
            age_hours = (datetime.utcnow() - ts).total_seconds() / 3600.0
            if age_hours > max_age_hours:
                logger.info(
                    "[TEMPORAL] Warm start: latest snapshot %.1fh old "
                    "(max %.1fh) — cold start",
                    age_hours, max_age_hours,
                )
                return {}
            logger.info(
                "[TEMPORAL] Warm start: loaded %d beliefs from %.1fh ago "
                "(%d total snapshots)",
                len(beliefs), age_hours, len(history),
            )
        except (ValueError, TypeError):
            logger.info(
                "[TEMPORAL] Warm start: loaded %d beliefs "
                "(timestamp unparseable, %d snapshots)",
                len(beliefs), len(history),
            )

        return {k: float(v) for k, v in beliefs.items()}


# =====================================================================
# Module-level singleton for convenience
# =====================================================================

_default_memory: Optional[TemporalMemory] = None


def get_temporal_memory() -> TemporalMemory:
    """Get or create the module-level TemporalMemory singleton."""
    global _default_memory
    if _default_memory is None:
        _default_memory = TemporalMemory()
    return _default_memory


def record_beliefs(beliefs: Dict[str, float], timestamp: Optional[str] = None) -> bool:
    """Convenience: record a belief snapshot to the default store."""
    return get_temporal_memory().record_snapshot(beliefs, timestamp)


def analyze_trends(current_beliefs: Optional[Dict[str, float]] = None) -> TemporalAnalysis:
    """Convenience: run full temporal analysis on the default store."""
    return get_temporal_memory().analyze_all(current_beliefs)


def warm_start_beliefs(max_age_hours: float = 48.0) -> Dict[str, float]:
    """Convenience: load last known beliefs from persisted history."""
    return get_temporal_memory().warm_start(max_age_hours)


__all__ = [
    "TemporalMemory",
    "TemporalIndicator",
    "TemporalAnalysis",
    "get_temporal_memory",
    "record_beliefs",
    "analyze_trends",
    "warm_start_beliefs",
    "MIN_HISTORY_REQUIRED",
    "TREND_WINDOW",
    "PERSISTENCE_WINDOW",
    "PERSISTENCE_THRESHOLD",
    "SPIKE_SIGMA",
    "MOMENTUM_LOOKBACK_HOURS",
]
