"""
Layer6_Backtesting — Calibration Metrics
=========================================

Computes quantitative backtesting metrics from ReplayResult objects:

    - Lead time: days between first prob_up ≥ 0.60 and escalation peak
    - False positives: expansion HIGH days that did NOT precede a peak
    - Brier score: mean squared error of prob_up vs. binary outcome
    - Gate stability: % of days the SRE risk level stayed stable
    - Acceleration watch accuracy: did acceleration_watch fire before peak?

Phase 6 ONLY.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from engine.Layer6_Backtesting.replay_engine import ReplayResult

log = logging.getLogger("backtesting.metrics")


# ── Constants ────────────────────────────────────────────────────────

PROB_UP_THRESHOLD = 0.60        # P(UP) ≥ this → "predicted escalation"
ESCALATION_WINDOW_DAYS = 14     # prediction must occur within this many days


# ── Data Structures ──────────────────────────────────────────────────

@dataclass
class CrisisMetrics:
    """Calibration metrics for a single crisis backtest."""
    crisis_name: str
    lead_time_days: Optional[int] = None    # None if never predicted
    false_positive_days: int = 0
    brier_score: float = 0.0
    gate_stability: float = 0.0             # 0-1 fraction
    acceleration_triggered: bool = False
    acceleration_lead_days: Optional[int] = None
    prewar_triggered: bool = False
    prewar_lead_days: Optional[int] = None
    peak_sre: float = 0.0
    peak_prob_up: float = 0.0
    total_days: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "crisis_name": self.crisis_name,
            "lead_time_days": self.lead_time_days,
            "false_positive_days": self.false_positive_days,
            "brier_score": round(self.brier_score, 4),
            "gate_stability": round(self.gate_stability, 4),
            "acceleration_triggered": self.acceleration_triggered,
            "acceleration_lead_days": self.acceleration_lead_days,
            "prewar_triggered": self.prewar_triggered,
            "prewar_lead_days": self.prewar_lead_days,
            "peak_sre": round(self.peak_sre, 4),
            "peak_prob_up": round(self.peak_prob_up, 4),
            "total_days": self.total_days,
            "error": self.error,
        }


# ── Metric Computation ──────────────────────────────────────────────

def _days_between(date_a: str, date_b: str) -> int:
    """Days from date_a to date_b (positive if b is later)."""
    a = datetime.strptime(date_a, "%Y-%m-%d")
    b = datetime.strptime(date_b, "%Y-%m-%d")
    return (b - a).days


def compute_lead_time(result: ReplayResult) -> Optional[int]:
    """
    Days between first prob_up ≥ PROB_UP_THRESHOLD and escalation peak.
    Returns None if threshold was never crossed.
    """
    for snap in result.snapshots:
        if snap.prob_up >= PROB_UP_THRESHOLD:
            return _days_between(snap.date, result.escalation_peak)
    return None


def compute_false_positives(result: ReplayResult) -> int:
    """
    Count days where expansion_mode == HIGH but the date is more than
    ESCALATION_WINDOW_DAYS before the peak (i.e. too early to be useful).
    """
    count = 0
    for snap in result.snapshots:
        if snap.expansion_mode == "HIGH":
            days_to_peak = _days_between(snap.date, result.escalation_peak)
            if days_to_peak > ESCALATION_WINDOW_DAYS:
                count += 1
    return count


def compute_brier_score(result: ReplayResult) -> float:
    """
    Brier score: mean of (prob_up - outcome)² across all days.

    Outcome = 1.0 on escalation_peak day, 0.0 otherwise.
    Lower is better (0 = perfect).
    """
    if not result.snapshots:
        return 1.0

    total = 0.0
    for snap in result.snapshots:
        outcome = 1.0 if snap.date == result.escalation_peak else 0.0
        total += (snap.prob_up - outcome) ** 2
    return total / len(result.snapshots)


def compute_gate_stability(result: ReplayResult) -> float:
    """
    Fraction of consecutive day-pairs where risk_level stayed the same.
    Higher = more stable (fewer oscillations).
    """
    if len(result.snapshots) < 2:
        return 1.0

    stable_count = 0
    for i in range(1, len(result.snapshots)):
        if result.snapshots[i].risk_level == result.snapshots[i - 1].risk_level:
            stable_count += 1
    return stable_count / (len(result.snapshots) - 1)


def compute_crisis_metrics(result: ReplayResult) -> CrisisMetrics:
    """Compute all calibration metrics for a single crisis replay."""
    if result.error:
        return CrisisMetrics(
            crisis_name=result.crisis_name,
            error=result.error,
        )

    metrics = CrisisMetrics(crisis_name=result.crisis_name)
    metrics.total_days = result.days_count
    metrics.peak_sre = result.peak_sre
    metrics.peak_prob_up = result.peak_prob_up

    # Lead time
    metrics.lead_time_days = compute_lead_time(result)

    # False positives
    metrics.false_positive_days = compute_false_positives(result)

    # Brier score
    metrics.brier_score = compute_brier_score(result)

    # Gate stability
    metrics.gate_stability = compute_gate_stability(result)

    # Acceleration watch
    for snap in result.snapshots:
        if snap.acceleration_watch:
            metrics.acceleration_triggered = True
            metrics.acceleration_lead_days = _days_between(
                snap.date, result.escalation_peak
            )
            break

    # Pre-war warning
    for snap in result.snapshots:
        if snap.pre_war_warning:
            metrics.prewar_triggered = True
            metrics.prewar_lead_days = _days_between(
                snap.date, result.escalation_peak
            )
            break

    log.info(f"[Metrics] {result.crisis_name}: "
             f"lead={metrics.lead_time_days}d, "
             f"FP={metrics.false_positive_days}, "
             f"Brier={metrics.brier_score:.4f}, "
             f"gate_stab={metrics.gate_stability:.2f}")

    return metrics


def compute_aggregate_metrics(
    results: List[ReplayResult],
) -> List[CrisisMetrics]:
    """Compute metrics for all replay results."""
    return [compute_crisis_metrics(r) for r in results]
