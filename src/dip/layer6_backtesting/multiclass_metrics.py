"""
layer6_backtesting.multiclass_metrics — Multi-Class Metrics
==========================================================

Full-spectrum evaluation metrics for the 5-state conflict model:

    1. **Multi-class Brier score** — Σ(p_k - o_k)² across 5 states
    2. **Per-state Brier** — decomposed by state
    3. **Transition accuracy** — top-1 and top-2 at horizon T+H
    4. **Escalation lead time** — when P(ACTIVE+) > threshold vs actual
    5. **Calibration curves** — per-state reliability diagrams

All metrics operate on ``DaySnapshot`` lists from ``ReplayResult``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("layer6_backtesting.multiclass_metrics")

STATES = ("PEACE", "TENSIONS", "ESCALATION", "CRISIS", "WAR")
_N = len(STATES)
_STATE_IDX = {s: i for i, s in enumerate(STATES)}

ESCALATION_STATES = ("ESCALATION", "CRISIS", "WAR")
P_ACTIVE_THRESHOLD = 0.50          # P(ACTIVE+) threshold for lead time
DEFAULT_HORIZON = 14               # forecast horizon in days
DEFAULT_CALIBRATION_BINS = 10      # number of bins for calibration curve


@dataclass
class CalibrationBin:
    """A single bin in a calibration curve."""
    bin_lower: float
    bin_upper: float
    mean_predicted: float = 0.0
    actual_frequency: float = 0.0
    count: int = 0


@dataclass
class MulticlassMetrics:
    """Aggregated multi-class evaluation metrics for one scenario."""
    scenario_name: str
    total_days: int = 0
    # ── Brier scores ──────────────────────────────────────────────
    multiclass_brier: float = 0.0
    per_state_brier: Dict[str, float] = field(default_factory=dict)
    # ── Transition accuracy ───────────────────────────────────────
    transition_accuracy_top1: float = 0.0
    transition_accuracy_top2: float = 0.0
    transition_horizon: int = DEFAULT_HORIZON
    transition_pairs_evaluated: int = 0
    # ── Escalation lead time ──────────────────────────────────────
    escalation_lead_time_days: Optional[int] = None
    first_prediction_date: Optional[str] = None
    first_actual_escalation_date: Optional[str] = None
    # ── Calibration curves ────────────────────────────────────────
    calibration_curves: Dict[str, List[CalibrationBin]] = field(default_factory=dict)
    # ── State accuracy ────────────────────────────────────────────
    map_accuracy: float = 0.0       # fraction where MAP state == ground truth
    confusion_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    # ── Dashboard-ready metrics ───────────────────────────────────
    binary_active_brier: float = 0.0   # Binary Brier for P(ACTIVE+)
    volatility_index: float = 0.0      # σ of P(ACTIVE+) over timeline
    false_positive_count: int = 0      # days P(ACTIVE+)>0.5 but GT≠ACTIVE+
    expected_calibration_error: float = 0.0  # ECE for P(ACTIVE+)
    # ── Error ─────────────────────────────────────────────────────
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "scenario_name": self.scenario_name,
            "total_days": self.total_days,
            "multiclass_brier": round(self.multiclass_brier, 6),
            "per_state_brier": {
                k: round(v, 6) for k, v in self.per_state_brier.items()
            },
            "transition_accuracy_top1": round(self.transition_accuracy_top1, 4),
            "transition_accuracy_top2": round(self.transition_accuracy_top2, 4),
            "transition_horizon": self.transition_horizon,
            "transition_pairs_evaluated": self.transition_pairs_evaluated,
            "escalation_lead_time_days": self.escalation_lead_time_days,
            "first_prediction_date": self.first_prediction_date,
            "first_actual_escalation_date": self.first_actual_escalation_date,
            "map_accuracy": round(self.map_accuracy, 4),
            "calibration_curves": {
                state: [
                    {
                        "bin_lower": round(b.bin_lower, 2),
                        "bin_upper": round(b.bin_upper, 2),
                        "mean_predicted": round(b.mean_predicted, 4),
                        "actual_frequency": round(b.actual_frequency, 4),
                        "count": b.count,
                    }
                    for b in bins
                ]
                for state, bins in self.calibration_curves.items()
            },
            "confusion_counts": self.confusion_counts,
            "binary_active_brier": round(self.binary_active_brier, 6),
            "volatility_index": round(self.volatility_index, 6),
            "false_positive_count": self.false_positive_count,
            "expected_calibration_error": round(self.expected_calibration_error, 6),
            "error": self.error,
        }


def _one_hot(state: str) -> Dict[str, float]:
    """One-hot vector for a state."""
    return {s: (1.0 if s == state else 0.0) for s in STATES}


def _get_val(obj: Any, attr: str, default: Any = 0.0) -> Any:
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def multiclass_brier_score(snapshots: list) -> float:
    if not snapshots:
        return 2.0  # worst case

    total = 0.0
    for snap in snapshots:
        gt = _get_val(snap, "ground_truth_state", "")
        gt_one_hot = _one_hot(gt)
        posterior = _get_val(snap, "conflict_posterior", {}) or {}
        for state in STATES:
            p = posterior.get(state, 0.0)
            o = gt_one_hot[state]
            total += (p - o) ** 2

    return total / len(snapshots)


def per_state_brier(snapshots: list) -> Dict[str, float]:
    if not snapshots:
        return {s: 1.0 for s in STATES}

    totals = {s: 0.0 for s in STATES}
    for snap in snapshots:
        gt = _get_val(snap, "ground_truth_state", "")
        gt_one_hot = _one_hot(gt)
        posterior = _get_val(snap, "conflict_posterior", {}) or {}
        for state in STATES:
            p = posterior.get(state, 0.0)
            o = gt_one_hot[state]
            totals[state] += (p - o) ** 2

    return {s: totals[s] / len(snapshots) for s in STATES}


def transition_accuracy_top1(
    snapshots: list,
    horizon: int = DEFAULT_HORIZON,
) -> Tuple[float, int]:
    if len(snapshots) <= horizon:
        return (0.0, 0)

    correct = 0
    total = 0
    for i in range(len(snapshots) - horizon):
        predicted_state = _get_val(snapshots[i], "conflict_state", "")
        actual_state = _get_val(snapshots[i + horizon], "ground_truth_state", "")
        if predicted_state == actual_state:
            correct += 1
        total += 1

    accuracy = correct / total if total > 0 else 0.0
    return (accuracy, total)


def transition_accuracy_top2(
    snapshots: list,
    horizon: int = DEFAULT_HORIZON,
) -> Tuple[float, int]:
    if len(snapshots) <= horizon:
        return (0.0, 0)

    correct = 0
    total = 0
    for i in range(len(snapshots) - horizon):
        posterior = _get_val(snapshots[i], "conflict_posterior", {}) or {}
        sorted_states = sorted(
            posterior.items(), key=lambda x: x[1], reverse=True
        )
        top2 = {s for s, _ in sorted_states[:2]}
        actual_state = _get_val(snapshots[i + horizon], "ground_truth_state", "")
        if actual_state in top2:
            correct += 1
        total += 1

    accuracy = correct / total if total > 0 else 0.0
    return (accuracy, total)


def escalation_lead_time(
    snapshots: list,
    threshold: float = P_ACTIVE_THRESHOLD,
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    first_prediction: Optional[str] = None
    first_actual: Optional[str] = None

    for snap in snapshots:
        posterior = _get_val(snap, "conflict_posterior", {}) or {}
        p_active = sum(posterior.get(s, 0.0) for s in ESCALATION_STATES)
        date = _get_val(snap, "date", "")
        gt = _get_val(snap, "ground_truth_state", "")

        if first_prediction is None and p_active > threshold:
            first_prediction = date

        if first_actual is None and gt in ESCALATION_STATES:
            first_actual = date

    if first_prediction is None or first_actual is None:
        return (None, first_prediction, first_actual)

    from datetime import datetime
    try:
        d_pred = datetime.strptime(first_prediction, "%Y-%m-%d")
        d_actual = datetime.strptime(first_actual, "%Y-%m-%d")
        lead_time = (d_actual - d_pred).days
        return (lead_time, first_prediction, first_actual)
    except Exception:
        return (None, first_prediction, first_actual)


def calibration_curve(
    snapshots: list,
    state: str,
    n_bins: int = DEFAULT_CALIBRATION_BINS,
) -> List[CalibrationBin]:
    if not snapshots or state not in STATES:
        return []

    bin_width = 1.0 / n_bins
    bins: List[CalibrationBin] = []

    for b in range(n_bins):
        lower = b * bin_width
        upper = (b + 1) * bin_width
        bins.append(CalibrationBin(bin_lower=lower, bin_upper=upper))

    for snap in snapshots:
        posterior = _get_val(snap, "conflict_posterior", {}) or {}
        p = posterior.get(state, 0.0)
        gt = _get_val(snap, "ground_truth_state", "")
        actual = 1.0 if gt == state else 0.0

        bin_idx = min(int(p / bin_width), n_bins - 1)

        bins[bin_idx].count += 1
        bins[bin_idx].mean_predicted += p
        bins[bin_idx].actual_frequency += actual

    for b in bins:
        if b.count > 0:
            b.mean_predicted /= b.count
            b.actual_frequency /= b.count

    return bins


def all_calibration_curves(
    snapshots: list,
    n_bins: int = DEFAULT_CALIBRATION_BINS,
) -> Dict[str, List[CalibrationBin]]:
    return {
        state: calibration_curve(snapshots, state, n_bins)
        for state in STATES
    }


def map_state_accuracy(snapshots: list) -> float:
    if not snapshots:
        return 0.0
    correct = 0
    for s in snapshots:
        c_state = _get_val(s, "conflict_state", "")
        gt = _get_val(s, "ground_truth_state", "")
        if c_state == gt:
            correct += 1
    return correct / len(snapshots)


def confusion_matrix(snapshots: list) -> Dict[str, Dict[str, int]]:
    matrix: Dict[str, Dict[str, int]] = {
        s: {a: 0 for a in STATES} for s in STATES
    }
    for snap in snapshots:
        pred = _get_val(snap, "conflict_state", "")
        actual = _get_val(snap, "ground_truth_state", "")
        if pred in matrix and actual in matrix[pred]:
            matrix[pred][actual] += 1
    return matrix


def binary_active_brier_score(snapshots: list) -> float:
    if not snapshots:
        return 1.0
    total = 0.0
    for snap in snapshots:
        posterior = _get_val(snap, "conflict_posterior", {}) or {}
        p = sum(posterior.get(s, 0.0) for s in ESCALATION_STATES)
        gt = _get_val(snap, "ground_truth_state", "")
        actual = 1.0 if gt in ESCALATION_STATES else 0.0
        total += (p - actual) ** 2
    return total / len(snapshots)


def compute_volatility_index(snapshots: list) -> float:
    if len(snapshots) < 2:
        return 0.0
    values = []
    for snap in snapshots:
        posterior = _get_val(snap, "conflict_posterior", {}) or {}
        p = sum(posterior.get(s, 0.0) for s in ESCALATION_STATES)
        values.append(p)
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return variance ** 0.5


def count_false_positives(
    snapshots: list,
    threshold: float = P_ACTIVE_THRESHOLD,
) -> int:
    fp = 0
    for snap in snapshots:
        posterior = _get_val(snap, "conflict_posterior", {}) or {}
        p = sum(posterior.get(s, 0.0) for s in ESCALATION_STATES)
        gt = _get_val(snap, "ground_truth_state", "")
        if p > threshold and gt not in ESCALATION_STATES:
            fp += 1
    return fp


def compute_expected_calibration_error(
    snapshots: list,
    n_bins: int = DEFAULT_CALIBRATION_BINS,
) -> float:
    if not snapshots:
        return 1.0
    bin_width = 1.0 / n_bins
    bins_sum_p = [0.0] * n_bins
    bins_sum_actual = [0.0] * n_bins
    bins_count = [0] * n_bins

    for snap in snapshots:
        posterior = _get_val(snap, "conflict_posterior", {}) or {}
        p = sum(posterior.get(s, 0.0) for s in ESCALATION_STATES)
        gt = _get_val(snap, "ground_truth_state", "")
        actual = 1.0 if gt in ESCALATION_STATES else 0.0
        idx = min(int(p / bin_width), n_bins - 1)
        bins_sum_p[idx] += p
        bins_sum_actual[idx] += actual
        bins_count[idx] += 1

    n = len(snapshots)
    ece = 0.0
    for b in range(n_bins):
        if bins_count[b] > 0:
            avg_p = bins_sum_p[b] / bins_count[b]
            avg_a = bins_sum_actual[b] / bins_count[b]
            ece += (bins_count[b] / n) * abs(avg_a - avg_p)
    return ece


def compute_all_metrics(
    snapshots: list,
    scenario_name: str = "",
    horizon: int = DEFAULT_HORIZON,
) -> MulticlassMetrics:
    if not snapshots:
        return MulticlassMetrics(
            scenario_name=scenario_name,
            error="No snapshots to evaluate",
        )

    try:
        mc_brier = multiclass_brier_score(snapshots)
        ps_brier = per_state_brier(snapshots)

        top1_acc, top1_n = transition_accuracy_top1(snapshots, horizon)
        top2_acc, top2_n = transition_accuracy_top2(snapshots, horizon)

        lead, pred_date, actual_date = escalation_lead_time(snapshots)

        cal_curves = all_calibration_curves(snapshots)

        map_acc = map_state_accuracy(snapshots)
        conf_matrix = confusion_matrix(snapshots)

        bin_brier = binary_active_brier_score(snapshots)
        vol_idx = compute_volatility_index(snapshots)
        fp_count = count_false_positives(snapshots)
        ece = compute_expected_calibration_error(snapshots)

        metrics = MulticlassMetrics(
            scenario_name=scenario_name,
            total_days=len(snapshots),
            multiclass_brier=mc_brier,
            per_state_brier=ps_brier,
            transition_accuracy_top1=top1_acc,
            transition_accuracy_top2=top2_acc,
            transition_horizon=horizon,
            transition_pairs_evaluated=top1_n,
            escalation_lead_time_days=lead,
            first_prediction_date=pred_date,
            first_actual_escalation_date=actual_date,
            calibration_curves=cal_curves,
            map_accuracy=map_acc,
            confusion_counts=conf_matrix,
            binary_active_brier=bin_brier,
            volatility_index=vol_idx,
            false_positive_count=fp_count,
            expected_calibration_error=ece,
        )

        logger.info(
            "[Metrics] %s: Brier=%.4f MAP_acc=%.2f%% top1=%.2f%% "
            "top2=%.2f%% lead=%s days",
            scenario_name,
            mc_brier,
            map_acc * 100,
            top1_acc * 100,
            top2_acc * 100,
            lead,
        )

        return metrics

    except Exception as exc:
        logger.error("[Metrics] Error computing metrics for %s: %s", scenario_name, exc)
        return MulticlassMetrics(
            scenario_name=scenario_name,
            error=str(exc),
        )
