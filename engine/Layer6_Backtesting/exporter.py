"""
Layer6_Backtesting — Dashboard JSON Exporter
===============================================

Produces dashboard-ready JSON for:
- Streamlit / React / D3.js visualization
- Jupyter analytics
- BI tools (Power BI, Tableau)

Output format includes per-day timeline with probability evolution,
aggregate metrics, calibration data, and learning drift analysis.

Each scenario becomes a self-contained JSON file under
``data/backtesting/results/`` that any front-end can consume directly.

Phase 6 — Full-Spectrum Backtesting.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from engine.Layer3_StateModel.conflict_state_model import STATES, _STATE_IDX
from engine.Layer6_Backtesting.multiclass_metrics import (
    ESCALATION_STATES,
    MulticlassMetrics,
)
from engine.Layer6_Backtesting.replay_engine import DaySnapshot, ReplayResult

log = logging.getLogger("backtesting.exporter")

MODEL_VERSION = "DIP5_Phase6_v1"

_EXPORT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "backtesting", "results"
)


# ══════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════

def _day_brier(snap: DaySnapshot) -> float:
    """Single-day multi-class Brier score: Σ_k (p_k - o_k)²."""
    total = 0.0
    for state in STATES:
        p = snap.conflict_posterior.get(state, 0.0)
        o = 1.0 if snap.ground_truth_state == state else 0.0
        total += (p - o) ** 2
    return total


def _p_active_plus(snap: DaySnapshot) -> float:
    """P(ACTIVE_CONFLICT) + P(FULL_WAR)."""
    return (
        snap.conflict_posterior.get("ACTIVE_CONFLICT", 0.0)
        + snap.conflict_posterior.get("FULL_WAR", 0.0)
    )


# ══════════════════════════════════════════════════════════════════════
#  TIMELINE ENTRY
# ══════════════════════════════════════════════════════════════════════

def _build_timeline_entry(
    snap: DaySnapshot,
    idx: int,
    snapshots: List[DaySnapshot],
) -> Dict[str, Any]:
    """
    Build a single timeline entry for the dashboard JSON.

    Includes per-day probability vector, confidence, gaps,
    transition matrix row, per-day Brier, and 14-day look-ahead
    actual outcome (if available in the replay window).
    """
    # ── 14-day look-ahead ─────────────────────────────────────────
    actual_outcome_14d: Optional[int] = None
    actual_state_14d: Optional[str] = None
    if idx + 14 < len(snapshots):
        gt_14d = snapshots[idx + 14].ground_truth_state
        actual_outcome_14d = 1 if gt_14d in ESCALATION_STATES else 0
        actual_state_14d = gt_14d

    # ── Gap analysis ──────────────────────────────────────────────
    gap_groups = [
        g for g, v in snap.observed_groups.items() if v < 0.02
    ]

    # ── Transition matrix row (current state) ─────────────────────
    tm_row = snap.transition_matrix_row if snap.transition_matrix_row else []

    return {
        "date": snap.date,
        "state_probs": {
            k: round(v, 4) for k, v in snap.conflict_posterior.items()
        },
        "map_state": snap.conflict_state,
        "p_active_plus": round(_p_active_plus(snap), 4),
        "p_active_plus_14d": round(snap.p_active_or_higher_14d, 4),
        "escalation_score": round(snap.sre, 4),
        "confidence": round(snap.conflict_confidence, 4),
        "gaps": snap.gap_count,
        "gap_groups": gap_groups,
        "transition_matrix_row": [round(v, 6) for v in tm_row],
        "ground_truth": snap.ground_truth_state,
        "actual_outcome_14d": actual_outcome_14d,
        "actual_state_14d": actual_state_14d,
        "brier": round(_day_brier(snap), 6),
        "learning_delta": {
            k: round(v, 6) for k, v in snap.learning_delta.items()
        },
    }


# ══════════════════════════════════════════════════════════════════════
#  LEARNING DRIFT
# ══════════════════════════════════════════════════════════════════════

def _build_learning_drift(result: ReplayResult) -> Dict[str, Any]:
    """
    Build learning drift section showing matrix evolution from
    expert baseline to post-learning state.

    Includes initial/final full matrices, per-state delta, and
    the CRISIS row specifically (most operationally relevant).
    """
    crisis_idx = _STATE_IDX.get("CRISIS", 1)

    initial_crisis_row = (
        result.matrix_before[crisis_idx]
        if len(result.matrix_before) > crisis_idx
        else []
    )
    final_crisis_row = (
        result.matrix_after[crisis_idx]
        if len(result.matrix_after) > crisis_idx
        else []
    )

    # CRISIS row delta
    crisis_delta = []
    if initial_crisis_row and final_crisis_row:
        crisis_delta = [
            round(final_crisis_row[i] - initial_crisis_row[i], 6)
            for i in range(min(len(initial_crisis_row), len(final_crisis_row)))
        ]

    # Full matrix delta
    delta_matrix: List[List[float]] = []
    for i in range(min(len(result.matrix_before), len(result.matrix_after))):
        row_delta = [
            round(
                result.matrix_after[i][j] - result.matrix_before[i][j], 6
            )
            for j in range(
                min(len(result.matrix_before[i]), len(result.matrix_after[i]))
            )
        ]
        delta_matrix.append(row_delta)

    return {
        "state_labels": list(STATES),
        "initial_matrix": [
            [round(v, 6) for v in row] for row in result.matrix_before
        ],
        "final_matrix": [
            [round(v, 6) for v in row] for row in result.matrix_after
        ],
        "delta_matrix": delta_matrix,
        "initial_crisis_row": [round(v, 6) for v in initial_crisis_row],
        "final_crisis_row": [round(v, 6) for v in final_crisis_row],
        "crisis_row_delta": crisis_delta,
    }


# ══════════════════════════════════════════════════════════════════════
#  METRICS BLOCK
# ══════════════════════════════════════════════════════════════════════

def _build_metrics_block(metrics: MulticlassMetrics) -> Dict[str, Any]:
    """
    Build the aggregate metrics block for the dashboard JSON.

    All values are rounded for clean serialization.
    """
    return {
        "multiclass_brier": round(metrics.multiclass_brier, 6),
        "binary_active_brier": round(metrics.binary_active_brier, 6),
        "per_state_brier": {
            k: round(v, 6) for k, v in metrics.per_state_brier.items()
        },
        "map_accuracy": round(metrics.map_accuracy, 4),
        "transition_accuracy_top1": round(
            metrics.transition_accuracy_top1, 4
        ),
        "transition_accuracy_top2": round(
            metrics.transition_accuracy_top2, 4
        ),
        "lead_time_days": metrics.escalation_lead_time_days,
        "first_prediction_date": metrics.first_prediction_date,
        "first_actual_escalation_date": (
            metrics.first_actual_escalation_date
        ),
        "false_positives": metrics.false_positive_count,
        "volatility": round(metrics.volatility_index, 6),
        "calibration_error": round(
            metrics.expected_calibration_error, 6
        ),
        "total_days": metrics.total_days,
        "calibration_buckets": {
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
            for state, bins in metrics.calibration_curves.items()
        },
        "confusion_matrix": metrics.confusion_counts,
    }


# ══════════════════════════════════════════════════════════════════════
#  PUBLIC API — Single Scenario Export
# ══════════════════════════════════════════════════════════════════════

def export_scenario_json(
    result: ReplayResult,
    metrics: MulticlassMetrics,
    window_size: int = 1,
    output_dir: Optional[str] = None,
) -> str:
    """
    Export a single scenario's results to dashboard-ready JSON.

    The output file is structured for direct consumption by any
    front-end visualization framework (Streamlit, React, D3.js,
    Jupyter, BI tools).

    Parameters
    ----------
    result : ReplayResult
        The replay output with day-by-day snapshots.
    metrics : MulticlassMetrics
        Computed evaluation metrics for this scenario.
    window_size : int
        The sliding window size used during replay (1 = daily).
    output_dir : str, optional
        Custom output directory.  Defaults to ``data/backtesting/results/``.

    Returns
    -------
    str — path to the written JSON file.
    """
    out_dir = output_dir or _EXPORT_DIR
    os.makedirs(out_dir, exist_ok=True)

    # ── Timeline ──────────────────────────────────────────────────
    timeline = [
        _build_timeline_entry(snap, idx, result.snapshots)
        for idx, snap in enumerate(result.snapshots)
    ]

    # ── Full export structure ─────────────────────────────────────
    export: Dict[str, Any] = {
        "scenario": result.scenario_name,
        "window_size": window_size,
        "model_version": MODEL_VERSION,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_days": result.days_count,
        "peak_p_active_plus": round(result.peak_p_active, 4),
        "ground_truth_phases": result.ground_truth_phases,
        "timeline": timeline,
        "metrics": _build_metrics_block(metrics),
        "learning_drift": _build_learning_drift(result),
    }

    # ── Write ─────────────────────────────────────────────────────
    safe_name = result.scenario_name.replace(" ", "_").lower()
    path = os.path.join(out_dir, f"{safe_name}.json")

    with open(path, "w") as f:
        json.dump(export, f, indent=2)

    size_kb = os.path.getsize(path) / 1024
    log.info(
        "[Exporter] Written %s (%d days, %.1f KB)",
        path, len(timeline), size_kb,
    )

    return path


# ══════════════════════════════════════════════════════════════════════
#  PUBLIC API — Batch Export + Index
# ══════════════════════════════════════════════════════════════════════

def export_all_scenarios(
    results: List[ReplayResult],
    all_metrics: List[MulticlassMetrics],
    aggregate: Optional[Dict[str, Any]] = None,
    window_size: int = 1,
    output_dir: Optional[str] = None,
) -> List[str]:
    """
    Export all scenario results and produce an aggregate index file.

    Parameters
    ----------
    results : list[ReplayResult]
    all_metrics : list[MulticlassMetrics]
    aggregate : dict, optional
        Cross-scenario aggregate report (from ``evaluator.aggregate_report``).
    window_size : int
        Sliding window size used during replay.
    output_dir : str, optional
        Custom output directory.

    Returns
    -------
    list[str] — paths to all written files (scenario JSONs + index.json).
    """
    paths: List[str] = []

    for result, metrics in zip(results, all_metrics):
        path = export_scenario_json(
            result, metrics, window_size, output_dir
        )
        paths.append(path)

    # ── Aggregate index ───────────────────────────────────────────
    out_dir = output_dir or _EXPORT_DIR
    index: Dict[str, Any] = {
        "model_version": MODEL_VERSION,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_size": window_size,
        "scenarios": [r.scenario_name for r in results],
        "scenario_files": [os.path.basename(p) for p in paths],
        "aggregate": aggregate or {},
    }

    idx_path = os.path.join(out_dir, "index.json")
    with open(idx_path, "w") as f:
        json.dump(index, f, indent=2)

    paths.append(idx_path)

    log.info(
        "[Exporter] Exported %d scenarios + index to %s",
        len(results), out_dir,
    )

    return paths


__all__ = [
    "export_scenario_json",
    "export_all_scenarios",
    "MODEL_VERSION",
]
