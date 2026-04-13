"""
Layer6_Backtesting — Evaluator
================================

Post-replay evaluation engine.

Capabilities:
    1. Evaluate a single scenario's replay result → MulticlassMetrics
    2. Batch-evaluate all scenarios
    3. Shadow minister comparison — two-pass delta analysis
    4. Aggregate cross-scenario report

Phase 6 — Full-Spectrum Backtesting.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any, Dict, List, Optional

from engine.Layer6_Backtesting.multiclass_metrics import (
    MulticlassMetrics,
    compute_all_metrics,
)
from engine.Layer6_Backtesting.replay_engine import (
    ReplayResult,
    replay_scenario,
)
from engine.Layer6_Backtesting.scenario_registry import BacktestScenario

log = logging.getLogger("backtesting.evaluator")


# ══════════════════════════════════════════════════════════════════════
#  1.  SINGLE SCENARIO EVALUATION
# ══════════════════════════════════════════════════════════════════════

def evaluate_scenario(result: ReplayResult) -> MulticlassMetrics:
    """
    Compute full multi-class metrics from a single replay result.

    Parameters
    ----------
    result : ReplayResult

    Returns
    -------
    MulticlassMetrics
    """
    if result.error:
        return MulticlassMetrics(
            scenario_name=result.scenario_name,
            error=f"Replay had error: {result.error}",
        )

    return compute_all_metrics(
        snapshots=result.snapshots,
        scenario_name=result.scenario_name,
    )


# ══════════════════════════════════════════════════════════════════════
#  2.  BATCH EVALUATION
# ══════════════════════════════════════════════════════════════════════

def evaluate_all(results: List[ReplayResult]) -> List[MulticlassMetrics]:
    """
    Compute metrics for all replay results.

    Parameters
    ----------
    results : list[ReplayResult]

    Returns
    -------
    list[MulticlassMetrics]
    """
    metrics_list: List[MulticlassMetrics] = []
    for result in results:
        m = evaluate_scenario(result)
        metrics_list.append(m)
    return metrics_list


# ══════════════════════════════════════════════════════════════════════
#  3.  SHADOW MINISTER COMPARISON
# ══════════════════════════════════════════════════════════════════════

def shadow_comparison(
    scenario: BacktestScenario,
) -> Dict[str, Any]:
    """
    Two-pass evaluation to measure minister impact.

    Pass 1:  COUNCIL_SHADOW_MODE = True  (ministers disabled / structural only)
    Pass 2:  COUNCIL_SHADOW_MODE = False (ministers enabled)

    Both passes start from identical deepcopy of expert baseline
    transition matrix for fair comparison.

    Returns
    -------
    dict with:
        - structural_metrics: MulticlassMetrics from Pass 1
        - minister_metrics: MulticlassMetrics from Pass 2
        - delta: dict of deltas comparing the two passes
    """
    log.info("[Shadow] ═══ Starting shadow comparison for: %s ═══", scenario.name)

    # Store original env values
    prev_shadow = os.environ.get("COUNCIL_SHADOW_MODE", "true")

    # ── Pass 1: Structural only (ministers disabled) ───────────────
    log.info("[Shadow] Pass 1: COUNCIL_SHADOW_MODE = True (disabled)")
    os.environ["COUNCIL_SHADOW_MODE"] = "true"
    result_structural = replay_scenario(scenario, enable_learning=True)
    metrics_structural = evaluate_scenario(result_structural)

    # ── Pass 2: Ministers enabled ──────────────────────────────────
    log.info("[Shadow] Pass 2: COUNCIL_SHADOW_MODE = False (enabled)")
    os.environ["COUNCIL_SHADOW_MODE"] = "false"
    result_minister = replay_scenario(scenario, enable_learning=True)
    metrics_minister = evaluate_scenario(result_minister)

    # ── Restore ───────────────────────────────────────────────────
    os.environ["COUNCIL_SHADOW_MODE"] = prev_shadow

    # ── Compute deltas ─────────────────────────────────────────────
    delta = _compute_delta(metrics_structural, metrics_minister)

    log.info(
        "[Shadow] ═══ Comparison complete for %s ═══\n"
        "  Brier delta: %+.4f (negative = minister improved)\n"
        "  MAP accuracy delta: %+.2f%%\n"
        "  Lead time delta: %s days",
        scenario.name,
        delta.get("brier_delta", 0.0),
        delta.get("map_accuracy_delta", 0.0) * 100,
        delta.get("lead_time_delta", "N/A"),
    )

    return {
        "scenario_name": scenario.name,
        "structural_metrics": metrics_structural.to_dict(),
        "minister_metrics": metrics_minister.to_dict(),
        "delta": delta,
    }


def _compute_delta(
    structural: MulticlassMetrics,
    minister: MulticlassMetrics,
) -> Dict[str, Any]:
    """
    Compute deltas between structural-only and minister-enabled runs.

    Negative values in Brier delta mean ministers improved accuracy.
    Positive values in accuracy delta mean ministers improved detection.
    """
    delta: Dict[str, Any] = {}

    # Brier score delta (lower is better, so negative means improvement)
    delta["brier_delta"] = minister.multiclass_brier - structural.multiclass_brier

    # Per-state Brier deltas
    delta["per_state_brier_delta"] = {
        state: minister.per_state_brier.get(state, 0.0)
             - structural.per_state_brier.get(state, 0.0)
        for state in structural.per_state_brier
    }

    # MAP accuracy delta (higher is better, so positive means improvement)
    delta["map_accuracy_delta"] = (
        minister.map_accuracy - structural.map_accuracy
    )

    # Transition accuracy deltas
    delta["top1_accuracy_delta"] = (
        minister.transition_accuracy_top1 - structural.transition_accuracy_top1
    )
    delta["top2_accuracy_delta"] = (
        minister.transition_accuracy_top2 - structural.transition_accuracy_top2
    )

    # Lead time delta
    s_lead = structural.escalation_lead_time_days
    m_lead = minister.escalation_lead_time_days
    if s_lead is not None and m_lead is not None:
        delta["lead_time_delta"] = m_lead - s_lead
    else:
        delta["lead_time_delta"] = None

    # Confidence improvement (average posterior confidence)
    s_conf = _avg_confidence(structural)
    m_conf = _avg_confidence(minister)
    delta["confidence_improvement"] = m_conf - s_conf

    # Overreaction count: days where minister predicts ACTIVE+ but ground truth is PEACE
    # (can only be computed from raw snapshots — use the metrics as proxy)
    delta["structural_brier"] = structural.multiclass_brier
    delta["minister_brier"] = minister.multiclass_brier
    delta["structural_map_accuracy"] = structural.map_accuracy
    delta["minister_map_accuracy"] = minister.map_accuracy

    return delta


def _avg_confidence(metrics: MulticlassMetrics) -> float:
    """Estimate average confidence from per-state Brier (lower Brier ≈ higher confidence)."""
    if not metrics.per_state_brier:
        return 0.0
    # Use 1 - avg_brier as a proxy for confidence
    avg_brier = sum(metrics.per_state_brier.values()) / len(metrics.per_state_brier)
    return 1.0 - avg_brier


# ══════════════════════════════════════════════════════════════════════
#  4.  AGGREGATE CROSS-SCENARIO REPORT
# ══════════════════════════════════════════════════════════════════════

def aggregate_report(all_metrics: List[MulticlassMetrics]) -> Dict[str, Any]:
    """
    Compute aggregate statistics across multiple scenarios.

    Parameters
    ----------
    all_metrics : list[MulticlassMetrics]

    Returns
    -------
    dict with:
        - avg_brier: average multi-class Brier
        - avg_map_accuracy: average MAP state accuracy
        - avg_top1: average transition accuracy (top-1)
        - avg_top2: average transition accuracy (top-2)
        - avg_lead_time: average escalation lead time (excl. None)
        - worst_scenario: scenario with highest Brier
        - best_scenario: scenario with lowest Brier
        - calibration_tier: EXCELLENT / ACCEPTABLE / MISCALIBRATED
        - n_scenarios: total
        - n_with_errors: count of scenarios with errors
    """
    valid = [m for m in all_metrics if m.error is None and m.total_days > 0]
    n_with_errors = sum(1 for m in all_metrics if m.error is not None)

    if not valid:
        return {
            "n_scenarios": len(all_metrics),
            "n_with_errors": n_with_errors,
            "avg_brier": None,
            "verdict": "NO_DATA",
        }

    # Averages
    avg_brier = sum(m.multiclass_brier for m in valid) / len(valid)
    avg_map = sum(m.map_accuracy for m in valid) / len(valid)
    avg_top1 = sum(m.transition_accuracy_top1 for m in valid) / len(valid)
    avg_top2 = sum(m.transition_accuracy_top2 for m in valid) / len(valid)

    # Lead times (exclude None)
    lead_times = [
        m.escalation_lead_time_days for m in valid
        if m.escalation_lead_time_days is not None
    ]
    avg_lead = sum(lead_times) / len(lead_times) if lead_times else None

    # Best / worst
    worst = max(valid, key=lambda m: m.multiclass_brier)
    best = min(valid, key=lambda m: m.multiclass_brier)

    # Calibration tier
    if avg_brier < 0.30:
        tier = "EXCELLENT"
    elif avg_brier < 0.60:
        tier = "ACCEPTABLE"
    else:
        tier = "MISCALIBRATED"

    report = {
        "n_scenarios": len(all_metrics),
        "n_valid": len(valid),
        "n_with_errors": n_with_errors,
        "avg_multiclass_brier": round(avg_brier, 4),
        "avg_map_accuracy": round(avg_map, 4),
        "avg_transition_accuracy_top1": round(avg_top1, 4),
        "avg_transition_accuracy_top2": round(avg_top2, 4),
        "avg_escalation_lead_time_days": round(avg_lead, 1) if avg_lead is not None else None,
        "worst_scenario": worst.scenario_name,
        "worst_brier": round(worst.multiclass_brier, 4),
        "best_scenario": best.scenario_name,
        "best_brier": round(best.multiclass_brier, 4),
        "calibration_tier": tier,
    }

    # Verdict
    if tier == "EXCELLENT" and avg_map > 0.60:
        report["verdict"] = "PASS — Model well-calibrated across all conflict states"
    elif tier == "ACCEPTABLE":
        report["verdict"] = "PARTIAL — Calibration acceptable, refinement recommended"
    else:
        report["verdict"] = "FAIL — Model requires recalibration"

    log.info(
        "[Evaluator] Aggregate: %d scenarios, avg Brier=%.4f, "
        "avg MAP acc=%.2f%%, tier=%s",
        len(valid), avg_brier, avg_map * 100, tier,
    )

    return report


# ══════════════════════════════════════════════════════════════════════
#  5.  DIAGNOSTIC PERSISTENCE
# ══════════════════════════════════════════════════════════════════════

_EVAL_DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "backtesting"
)


def persist_evaluation(
    all_metrics: List[MulticlassMetrics],
    report: Optional[Dict[str, Any]] = None,
    filename: str = "evaluation_results.json",
) -> None:
    """
    Persist evaluation results to JSON for offline analysis.
    """
    try:
        os.makedirs(_EVAL_DATA_DIR, exist_ok=True)
        path = os.path.join(_EVAL_DATA_DIR, filename)
        data = {
            "scenarios": [m.to_dict() for m in all_metrics],
            "aggregate": report or {},
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        log.info("[Evaluator] Persisted evaluation to %s", path)
    except Exception as exc:
        log.warning("[Evaluator] Failed to persist evaluation: %s", exc)


__all__ = [
    "evaluate_scenario",
    "evaluate_all",
    "shadow_comparison",
    "aggregate_report",
    "persist_evaluation",
]
