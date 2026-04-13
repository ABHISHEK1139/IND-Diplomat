# Layer6_Backtesting — Historical Crisis Calibration (Phase 6)

from engine.Layer6_Backtesting.crisis_registry import CrisisWindow, CRISES, get_crisis_by_name
from engine.Layer6_Backtesting.replay_engine import (
    replay_crisis, replay_all, replay_scenario, replay_all_scenarios,
    ReplayResult, DaySnapshot,
)
from engine.Layer6_Backtesting.calibration_metrics import (
    compute_crisis_metrics, compute_aggregate_metrics, CrisisMetrics,
)
from engine.Layer6_Backtesting.evaluation_report import (
    format_evaluation_report, print_evaluation_report,
    format_full_spectrum_report, print_full_spectrum_report,
)
from engine.Layer6_Backtesting.scenario_registry import (
    BacktestScenario, StatePhase, SCENARIOS,
    get_scenario, get_ground_truth, get_one_hot,
    generate_synthetic_signals, build_mock_signals,
)
from engine.Layer6_Backtesting.multiclass_metrics import (
    MulticlassMetrics, multiclass_brier_score, per_state_brier,
    transition_accuracy_top1, transition_accuracy_top2,
    escalation_lead_time, calibration_curve, compute_all_metrics,
    binary_active_brier_score, compute_volatility_index,
    count_false_positives, compute_expected_calibration_error,
)
from engine.Layer6_Backtesting.evaluator import (
    evaluate_scenario, evaluate_all, shadow_comparison,
    aggregate_report, persist_evaluation,
)
from engine.Layer6_Backtesting.exporter import (
    export_scenario_json, export_all_scenarios, MODEL_VERSION,
)

__all__ = [
    # Crisis registry (legacy)
    "CrisisWindow", "CRISES", "get_crisis_by_name",
    # Replay engine
    "replay_crisis", "replay_all", "replay_scenario", "replay_all_scenarios",
    "ReplayResult", "DaySnapshot",
    # Binary metrics (legacy)
    "compute_crisis_metrics", "compute_aggregate_metrics", "CrisisMetrics",
    # Reports
    "format_evaluation_report", "print_evaluation_report",
    "format_full_spectrum_report", "print_full_spectrum_report",
    # Scenario registry
    "BacktestScenario", "StatePhase", "SCENARIOS",
    "get_scenario", "get_ground_truth", "get_one_hot",
    "generate_synthetic_signals", "build_mock_signals",
    # Multi-class metrics
    "MulticlassMetrics", "multiclass_brier_score", "per_state_brier",
    "transition_accuracy_top1", "transition_accuracy_top2",
    "escalation_lead_time", "calibration_curve", "compute_all_metrics",
    # Dashboard-ready metrics
    "binary_active_brier_score", "compute_volatility_index",
    "count_false_positives", "compute_expected_calibration_error",
    # Evaluator
    "evaluate_scenario", "evaluate_all", "shadow_comparison",
    "aggregate_report", "persist_evaluation",
    # Exporter
    "export_scenario_json", "export_all_scenarios", "MODEL_VERSION",
]
