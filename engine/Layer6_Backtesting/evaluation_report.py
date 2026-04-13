"""
Layer6_Backtesting — Evaluation Report
========================================

Generates human-readable summary of backtesting results across
all crisis windows.  Suitable for stdout / log output or for
inclusion in a Markdown report.

Supports both:
  - Legacy binary CrisisMetrics (Phase 6 original)
  - Full-spectrum MulticlassMetrics (Phase 6 upgrade)

Phase 6.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from engine.Layer6_Backtesting.calibration_metrics import CrisisMetrics

log = logging.getLogger("backtesting.report")


# ── Formatting Helpers ───────────────────────────────────────────────

def _bar(label: str, width: int = 60) -> str:
    return f"{'─' * width}\n{label}\n{'─' * width}"


def _metric_line(label: str, value, unit: str = "") -> str:
    if value is None:
        return f"  {label:<30s}  —"
    if isinstance(value, float):
        return f"  {label:<30s}  {value:.4f}{(' ' + unit) if unit else ''}"
    return f"  {label:<30s}  {value}{(' ' + unit) if unit else ''}"


def _bool_indicator(val: bool) -> str:
    return "YES ■" if val else "NO  □"


# ── Single Crisis Section ───────────────────────────────────────────

def format_crisis_section(m: CrisisMetrics) -> str:
    """Format a single crisis's metrics into a text block."""
    lines = [
        "",
        _bar(f"CRISIS: {m.crisis_name}"),
    ]

    if m.error:
        lines.append(f"  ERROR: {m.error}")
        return "\n".join(lines)

    lines.extend([
        _metric_line("Total days simulated", m.total_days, "days"),
        _metric_line("Peak SRE", m.peak_sre),
        _metric_line("Peak P(HIGH 14d)", m.peak_prob_up),
        "",
        "  ── Prediction Quality ──",
        _metric_line("Lead time to peak", m.lead_time_days, "days"),
        _metric_line("False positive days", m.false_positive_days, "days"),
        _metric_line("Brier score", m.brier_score),
        _metric_line("Gate stability", m.gate_stability),
        "",
        "  ── Warning Triggers ──",
        _metric_line("Pre-war warning", _bool_indicator(m.prewar_triggered)),
        _metric_line("Pre-war lead time", m.prewar_lead_days, "days"),
        _metric_line("Acceleration watch", _bool_indicator(m.acceleration_triggered)),
        _metric_line("Acceleration lead time", m.acceleration_lead_days, "days"),
    ])

    return "\n".join(lines)


# ── Aggregate Summary ───────────────────────────────────────────────

def format_aggregate_summary(metrics: List[CrisisMetrics]) -> str:
    """Format aggregate statistics across all crises."""
    valid = [m for m in metrics if m.error is None]
    if not valid:
        return "\n  No valid backtests to summarize.\n"

    # Lead time stats
    lead_times = [m.lead_time_days for m in valid if m.lead_time_days is not None]
    avg_lead = sum(lead_times) / len(lead_times) if lead_times else None
    detected = len(lead_times)
    total_crises = len(valid)

    # Brier
    avg_brier = sum(m.brier_score for m in valid) / len(valid)

    # Gate stability
    avg_stability = sum(m.gate_stability for m in valid) / len(valid)

    # Warning triggers
    prewar_count = sum(1 for m in valid if m.prewar_triggered)
    accel_count = sum(1 for m in valid if m.acceleration_triggered)

    lines = [
        "",
        _bar("AGGREGATE BACKTEST SUMMARY"),
        _metric_line("Crises tested", total_crises),
        _metric_line("Escalations detected", f"{detected}/{total_crises}"),
        _metric_line("Detection rate", f"{detected / total_crises * 100:.1f}%"),
        "",
        _metric_line("Avg lead time", avg_lead, "days"),
        _metric_line("Avg Brier score", avg_brier),
        _metric_line("Avg gate stability", avg_stability),
        "",
        _metric_line("Pre-war warnings fired", f"{prewar_count}/{total_crises}"),
        _metric_line("Acceleration watches fired", f"{accel_count}/{total_crises}"),
    ]

    # Pass/fail assessment
    lines.append("")
    if detected == total_crises and avg_brier < 0.25:
        lines.append("  VERDICT:  PASS — Model detected all crises with acceptable Brier")
    elif detected >= total_crises * 0.75:
        lines.append("  VERDICT:  PARTIAL — Most crises detected, calibration refinement needed")
    else:
        lines.append("  VERDICT:  FAIL — Insufficient detection rate, model recalibration required")

    return "\n".join(lines)


# ── Full Report ──────────────────────────────────────────────────────

def format_evaluation_report(metrics: List[CrisisMetrics]) -> str:
    """Generate the complete backtesting evaluation report."""
    sections = [
        "",
        "=" * 70,
        "  PHASE 6 — HISTORICAL BACKTESTING EVALUATION REPORT",
        "=" * 70,
    ]

    for m in metrics:
        sections.append(format_crisis_section(m))

    sections.append(format_aggregate_summary(metrics))

    sections.extend([
        "",
        "=" * 70,
        "  END OF BACKTESTING REPORT",
        "=" * 70,
        "",
    ])

    return "\n".join(sections)


def print_evaluation_report(metrics: List[CrisisMetrics]) -> None:
    """Print the full evaluation report to stdout and log."""
    report = format_evaluation_report(metrics)
    print(report)
    log.info(report)


# ══════════════════════════════════════════════════════════════════════
#  FULL-SPECTRUM MULTI-CLASS REPORT
# ══════════════════════════════════════════════════════════════════════

def format_multiclass_section(metrics: Any) -> str:
    """
    Format a single scenario's MulticlassMetrics into a text block.

    Parameters
    ----------
    metrics : MulticlassMetrics
    """
    lines = [
        "",
        _bar(f"SCENARIO: {metrics.scenario_name}"),
    ]

    if metrics.error:
        lines.append(f"  ERROR: {metrics.error}")
        return "\n".join(lines)

    lines.extend([
        _metric_line("Total days simulated", metrics.total_days, "days"),
        "",
        "  ── Multi-Class Brier Score ──",
        _metric_line("Overall Brier", metrics.multiclass_brier),
    ])

    # Per-state Brier table
    if metrics.per_state_brier:
        lines.append("")
        lines.append("  State                 Brier")
        lines.append("  " + "─" * 35)
        for state, brier in metrics.per_state_brier.items():
            lines.append(f"  {state:<22s}  {brier:.6f}")

    lines.extend([
        "",
        "  ── State Accuracy ──",
        _metric_line("MAP state accuracy", f"{metrics.map_accuracy * 100:.1f}%"),
    ])

    lines.extend([
        "",
        "  ── Transition Accuracy (T+{}) ──".format(metrics.transition_horizon),
        _metric_line("Top-1 accuracy", f"{metrics.transition_accuracy_top1 * 100:.1f}%"),
        _metric_line("Top-2 accuracy", f"{metrics.transition_accuracy_top2 * 100:.1f}%"),
        _metric_line("Pairs evaluated", metrics.transition_pairs_evaluated),
    ])

    lines.extend([
        "",
        "  ── Escalation Lead Time ──",
        _metric_line("Lead time", metrics.escalation_lead_time_days, "days"),
        _metric_line("First prediction", metrics.first_prediction_date),
        _metric_line("First actual escalation", metrics.first_actual_escalation_date),
    ])

    return "\n".join(lines)


def format_calibration_curves(metrics: Any) -> str:
    """
    Format calibration curve data as a tabular text block.

    Parameters
    ----------
    metrics : MulticlassMetrics
    """
    lines = [
        "",
        _bar(f"CALIBRATION CURVES: {metrics.scenario_name}"),
    ]

    if not metrics.calibration_curves:
        lines.append("  No calibration data available.")
        return "\n".join(lines)

    for state, bins in metrics.calibration_curves.items():
        lines.append(f"\n  State: {state}")
        lines.append("  Bin             Predicted   Actual     Count")
        lines.append("  " + "─" * 50)
        for b in bins:
            if b.count > 0:
                lines.append(
                    f"  [{b.bin_lower:.2f}-{b.bin_upper:.2f})   "
                    f"{b.mean_predicted:8.4f}   {b.actual_frequency:8.4f}   "
                    f"{b.count:5d}"
                )

    return "\n".join(lines)


def format_confusion_matrix(metrics: Any) -> str:
    """
    Format confusion matrix as a text block.

    Parameters
    ----------
    metrics : MulticlassMetrics
    """
    lines = [
        "",
        _bar(f"CONFUSION MATRIX: {metrics.scenario_name}"),
        "",
        "  Predicted \\ Actual   " + "  ".join(f"{s[:6]:>6s}" for s in _STATES_SHORT),
    ]
    lines.append("  " + "─" * 55)

    for pred in _STATES_SHORT:
        counts = metrics.confusion_counts.get(
            _SHORT_TO_FULL.get(pred, pred), {}
        )
        row_vals = [
            counts.get(_SHORT_TO_FULL.get(act, act), 0)
            for act in _STATES_SHORT
        ]
        lines.append(
            f"  {pred:>20s}   " + "  ".join(f"{v:6d}" for v in row_vals)
        )

    return "\n".join(lines)


# Short state names for table display
_STATES_SHORT = ["PEACE", "CRISIS", "LIM_ST", "ACT_CF", "FULLWR"]
_SHORT_TO_FULL = {
    "PEACE": "PEACE",
    "CRISIS": "CRISIS",
    "LIM_ST": "LIMITED_STRIKES",
    "ACT_CF": "ACTIVE_CONFLICT",
    "FULLWR": "FULL_WAR",
}


def format_shadow_comparison(delta: Dict[str, Any]) -> str:
    """
    Format shadow minister comparison results.

    Parameters
    ----------
    delta : dict
        Output from ``evaluator.shadow_comparison()``
    """
    lines = [
        "",
        _bar(f"SHADOW MINISTER COMPARISON: {delta.get('scenario_name', '?')}"),
        "",
        "  Pass 1 (structural only)  vs  Pass 2 (ministers enabled)",
        "",
        _metric_line(
            "Brier (structural)",
            delta.get("structural_brier"),
        ),
        _metric_line(
            "Brier (ministers)",
            delta.get("minister_brier"),
        ),
        _metric_line(
            "Brier delta",
            delta.get("brier_delta"),
        ),
        "",
        _metric_line(
            "MAP acc (structural)",
            f"{delta.get('structural_map_accuracy', 0) * 100:.1f}%",
        ),
        _metric_line(
            "MAP acc (ministers)",
            f"{delta.get('minister_map_accuracy', 0) * 100:.1f}%",
        ),
        _metric_line(
            "MAP acc delta",
            f"{delta.get('map_accuracy_delta', 0) * 100:+.1f}%",
        ),
        "",
        _metric_line("Lead time delta", delta.get("lead_time_delta"), "days"),
        _metric_line("Confidence improvement", delta.get("confidence_improvement")),
    ]

    return "\n".join(lines)


def format_multiclass_aggregate(report: Dict[str, Any]) -> str:
    """
    Format aggregate cross-scenario summary.

    Parameters
    ----------
    report : dict
        Output from ``evaluator.aggregate_report()``
    """
    lines = [
        "",
        _bar("FULL-SPECTRUM AGGREGATE SUMMARY"),
        _metric_line("Scenarios tested", report.get("n_valid", 0)),
        _metric_line("Scenarios with errors", report.get("n_with_errors", 0)),
        "",
        _metric_line("Avg multi-class Brier", report.get("avg_multiclass_brier")),
        _metric_line("Avg MAP accuracy", report.get("avg_map_accuracy")),
        _metric_line("Avg top-1 accuracy", report.get("avg_transition_accuracy_top1")),
        _metric_line("Avg top-2 accuracy", report.get("avg_transition_accuracy_top2")),
        _metric_line(
            "Avg escalation lead time",
            report.get("avg_escalation_lead_time_days"),
            "days",
        ),
        "",
        _metric_line("Best scenario", report.get("best_scenario")),
        _metric_line("Best Brier", report.get("best_brier")),
        _metric_line("Worst scenario", report.get("worst_scenario")),
        _metric_line("Worst Brier", report.get("worst_brier")),
        "",
        _metric_line("Calibration tier", report.get("calibration_tier")),
        "",
        f"  VERDICT:  {report.get('verdict', 'N/A')}",
    ]

    return "\n".join(lines)


def format_full_spectrum_report(
    all_metrics: list,
    aggregate: Optional[Dict[str, Any]] = None,
    include_calibration: bool = False,
    include_confusion: bool = False,
) -> str:
    """
    Generate the complete full-spectrum evaluation report.

    Parameters
    ----------
    all_metrics : list[MulticlassMetrics]
    aggregate : dict, optional
        Output from ``evaluator.aggregate_report()``.
    include_calibration : bool
        Whether to include per-state calibration curves.
    include_confusion : bool
        Whether to include confusion matrices.

    Returns
    -------
    str — formatted report text
    """
    sections = [
        "",
        "=" * 70,
        "  FULL-SPECTRUM BACKTESTING EVALUATION REPORT",
        "=" * 70,
    ]

    for m in all_metrics:
        sections.append(format_multiclass_section(m))
        if include_calibration:
            sections.append(format_calibration_curves(m))
        if include_confusion:
            sections.append(format_confusion_matrix(m))

    if aggregate:
        sections.append(format_multiclass_aggregate(aggregate))

    sections.extend([
        "",
        "=" * 70,
        "  END OF FULL-SPECTRUM REPORT",
        "=" * 70,
        "",
    ])

    return "\n".join(sections)


def print_full_spectrum_report(
    all_metrics: list,
    aggregate: Optional[Dict[str, Any]] = None,
    include_calibration: bool = False,
    include_confusion: bool = False,
) -> None:
    """Print the complete full-spectrum report to stdout and log."""
    report = format_full_spectrum_report(
        all_metrics, aggregate, include_calibration, include_confusion
    )
    print(report)
    log.info(report)
