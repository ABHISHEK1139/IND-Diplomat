"""
Layer6_Backtesting — Replay Engine (Full-Spectrum)
====================================================

Production replay engine for the Bayesian conflict state model.

Architecture
------------
For each scenario the engine:

1.  **Snapshots** the expert baseline transition matrix (``deepcopy``).
2.  Sets ``BACKTEST_MODE = True`` to prevent all disk persistence.
3.  Iterates day-by-day through the scenario's date range:
    a.  Generates signal data (synthetic from ground truth profile + noise,
        or from a pre-built file).
    b.  Calls ``classify_conflict_state()`` with in-memory prior/transition
        overrides — **no disk I/O**.
    c.  Optionally updates the in-memory transition matrix via bounded
        adaptive learning (reset per scenario — no carryover).
    d.  Records the full ``DaySnapshot`` including conflict posterior,
        ground truth, transition matrix row, and learning delta.
4.  Restores original ``BACKTEST_MODE`` state.
5.  Returns ``ReplayResult`` with matrix-before / matrix-after for
    comparison.

Temporal Isolation
------------------
- ``RuntimeClock`` is pinned via ``frozen_date()`` for each simulated day.
- No future data leaks — each day only sees signals up to that date.
- Per-scenario matrix starts from ``_EXPERT_TRANSITION`` (deepcopy).

Phase 6 — Full-Spectrum Backtesting.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from engine.Layer3_StateModel.conflict_state_model import (
    STATES,
    _EXPERT_TRANSITION,
    _N,
    _STATE_IDX,
    classify_conflict_state,
    update_transition_matrix,
)
from engine.Layer6_Backtesting.crisis_registry import CrisisWindow
from engine.Layer6_Backtesting.scenario_registry import (
    BacktestScenario,
    StatePhase,
    build_mock_signals,
    date_range,
    generate_synthetic_signals,
    get_ground_truth,
    get_one_hot,
)

log = logging.getLogger("backtesting.replay")


# ══════════════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════

@dataclass
class DaySnapshot:
    """A single day's output during replay."""
    date: str                                           # ISO date
    # ── Legacy fields (SRE/trajectory — kept for backward compat) ──
    sre: float = 0.0
    risk_level: str = "LOW"
    prob_up: float = 0.0
    prob_down: float = 0.0
    prob_stable: float = 1.0
    expansion_mode: str = "NONE"
    ndi: float = 0.0
    pre_war_warning: bool = False
    acceleration_watch: bool = False
    raw_domains: Dict[str, float] = field(default_factory=dict)
    # ── Full-spectrum conflict state fields ────────────────────────
    conflict_state: str = "UNKNOWN"
    conflict_posterior: Dict[str, float] = field(default_factory=dict)
    conflict_confidence: float = 0.0
    forecast_14d: Dict[str, float] = field(default_factory=dict)
    p_active_or_higher_14d: float = 0.0
    ground_truth_state: str = ""
    transition_matrix_row: List[float] = field(default_factory=list)
    learning_delta: Dict[str, float] = field(default_factory=dict)
    gap_count: int = 0
    observed_groups: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "sre": round(self.sre, 4),
            "risk_level": self.risk_level,
            "prob_up": round(self.prob_up, 4),
            "prob_down": round(self.prob_down, 4),
            "prob_stable": round(self.prob_stable, 4),
            "expansion_mode": self.expansion_mode,
            "ndi": round(self.ndi, 4),
            "pre_war_warning": self.pre_war_warning,
            "acceleration_watch": self.acceleration_watch,
            "raw_domains": {k: round(v, 4) for k, v in self.raw_domains.items()},
            "conflict_state": self.conflict_state,
            "conflict_posterior": {
                k: round(v, 4) for k, v in self.conflict_posterior.items()
            },
            "conflict_confidence": round(self.conflict_confidence, 4),
            "forecast_14d": {
                k: round(v, 4) for k, v in self.forecast_14d.items()
            },
            "p_active_or_higher_14d": round(self.p_active_or_higher_14d, 4),
            "ground_truth_state": self.ground_truth_state,
            "transition_matrix_row": [round(v, 6) for v in self.transition_matrix_row],
            "learning_delta": {
                k: round(v, 6) for k, v in self.learning_delta.items()
            },
            "gap_count": self.gap_count,
            "observed_groups": {
                k: round(v, 4) for k, v in self.observed_groups.items()
            },
        }


@dataclass
class ReplayResult:
    """Complete time-series for a backtest run."""
    crisis_name: str
    start: str
    escalation_peak: str
    snapshots: List[DaySnapshot] = field(default_factory=list)
    error: Optional[str] = None
    # ── Full-spectrum additions ────────────────────────────────────
    scenario_name: str = ""
    ground_truth_phases: List[Dict[str, str]] = field(default_factory=list)
    matrix_before: List[List[float]] = field(default_factory=list)
    matrix_after: List[List[float]] = field(default_factory=list)

    @property
    def days_count(self) -> int:
        return len(self.snapshots)

    @property
    def peak_sre(self) -> float:
        if not self.snapshots:
            return 0.0
        return max(s.sre for s in self.snapshots)

    @property
    def peak_prob_up(self) -> float:
        if not self.snapshots:
            return 0.0
        return max(s.prob_up for s in self.snapshots)

    @property
    def first_high_expansion_date(self) -> Optional[str]:
        """First date expansion_mode reached HIGH."""
        for s in self.snapshots:
            if s.expansion_mode == "HIGH":
                return s.date
        return None

    @property
    def first_prewar_warning_date(self) -> Optional[str]:
        """First date pre_war_warning fired."""
        for s in self.snapshots:
            if s.pre_war_warning:
                return s.date
        return None

    @property
    def peak_p_active(self) -> float:
        """Highest P(ACTIVE_CONFLICT) + P(FULL_WAR) across all days."""
        if not self.snapshots:
            return 0.0
        return max(
            s.conflict_posterior.get("ACTIVE_CONFLICT", 0.0)
            + s.conflict_posterior.get("FULL_WAR", 0.0)
            for s in self.snapshots
        )

    def to_dict(self) -> dict:
        return {
            "crisis_name": self.crisis_name,
            "scenario_name": self.scenario_name,
            "start": self.start,
            "escalation_peak": self.escalation_peak,
            "days_count": self.days_count,
            "peak_sre": round(self.peak_sre, 4),
            "peak_prob_up": round(self.peak_prob_up, 4),
            "peak_p_active": round(self.peak_p_active, 4),
            "first_high_expansion_date": self.first_high_expansion_date,
            "first_prewar_warning_date": self.first_prewar_warning_date,
            "ground_truth_phases": self.ground_truth_phases,
            "matrix_before": [
                [round(v, 6) for v in row] for row in self.matrix_before
            ],
            "matrix_after": [
                [round(v, 6) for v in row] for row in self.matrix_after
            ],
            "error": self.error,
            "snapshots": [s.to_dict() for s in self.snapshots],
        }


# ══════════════════════════════════════════════════════════════════════
#  REPLAY HELPERS
# ══════════════════════════════════════════════════════════════════════

def _count_signal_gaps(observed_groups: Dict[str, float]) -> int:
    """Count signal groups with zero or near-zero observation."""
    return sum(1 for v in observed_groups.values() if v < 0.02)


def _matrix_row_delta(
    before: List[float], after: List[float]
) -> Dict[str, float]:
    """Compute per-state delta between two transition matrix rows."""
    return {
        STATES[i]: after[i] - before[i]
        for i in range(_N)
    }


def _set_backtest_mode(enabled: bool) -> None:
    """Set BACKTEST_MODE flag via environment variable."""
    os.environ["BACKTEST_MODE"] = "true" if enabled else "false"


# ══════════════════════════════════════════════════════════════════════
#  SLIDING WINDOW SIGNAL AGGREGATION
# ══════════════════════════════════════════════════════════════════════

def _aggregate_window_signals(
    window_dates: List[str],
    scenario: BacktestScenario,
    base_day_index: int,
) -> Dict[str, float]:
    """
    Average synthetic signals across a sliding window of dates.

    For a 3-day window centred on day T, generates signals for
    [T-2, T-1, T] using each day's ground truth profile, then
    averages the signal-group values.  This smooths single-day
    noise while preserving regime transitions, matching how real
    intelligence assessments use rolling observation windows.

    Parameters
    ----------
    window_dates : list[str]
        ISO dates in the window (e.g. 3 dates for window_size=3).
    scenario : BacktestScenario
        Source of ground truth for signal generation.
    base_day_index : int
        0-based index of the primary (latest) day in the window.

    Returns
    -------
    Dict[str, float]  —  averaged signal group values.
    """
    all_groups: List[Dict[str, float]] = []
    for offset, date in enumerate(window_dates):
        gt = get_ground_truth(scenario, date)
        start_idx = base_day_index - len(window_dates) + 1 + offset
        seed = start_idx * 1000 + hash(date) % 10000
        groups = generate_synthetic_signals(gt, noise_sigma=0.08, seed=seed)
        all_groups.append(groups)

    if not all_groups:
        return {}

    averaged: Dict[str, float] = {}
    for group in all_groups[0]:
        averaged[group] = (
            sum(g.get(group, 0.0) for g in all_groups) / len(all_groups)
        )
    return averaged


# ══════════════════════════════════════════════════════════════════════
#  CORE SIMULATION
# ══════════════════════════════════════════════════════════════════════

def _simulate_day(
    date: str,
    scenario: BacktestScenario,
    current_prior: Dict[str, float],
    current_matrix: List[List[float]],
    prev_state: str,
    day_index: int,
    mock_signals_override: Optional[Dict[str, object]] = None,
) -> DaySnapshot:
    """
    Simulate a single day of the conflict state pipeline.

    Parameters
    ----------
    date : str
        ISO date for this simulation step.
    scenario : BacktestScenario
        The scenario being replayed (for ground truth + signal gen).
    current_prior : dict
        Prior state distribution (posterior from previous day).
    current_matrix : list[list[float]]
        Current adaptive transition matrix (in-memory, per-scenario).
    prev_state : str
        MAP state from the previous day (for adaptive learning).
    day_index : int
        0-based day counter (used as RNG seed for reproducibility).

    Returns
    -------
    DaySnapshot with all conflict state fields populated.
    """
    # ── 1. Ground truth ───────────────────────────────────────────
    gt_state = get_ground_truth(scenario, date)

    # ── 2. Generate signals (or use windowed override) ─────────────
    if mock_signals_override is not None:
        mock_signals = mock_signals_override
    elif scenario.signal_source == "synthetic":
        signal_groups = generate_synthetic_signals(
            gt_state, noise_sigma=0.08, seed=day_index * 1000 + hash(date) % 10000
        )
        mock_signals = build_mock_signals(signal_groups)
    else:
        # File/GDELT modes — fall back to synthetic for now
        signal_groups = generate_synthetic_signals(
            gt_state, noise_sigma=0.08, seed=day_index * 1000 + hash(date) % 10000
        )
        mock_signals = build_mock_signals(signal_groups)

    # ── 3. Record matrix row BEFORE update ────────────────────────
    current_state_idx = _STATE_IDX.get(prev_state, 0)
    row_before = current_matrix[current_state_idx][:]

    # ── 4. Classify conflict state ────────────────────────────────
    result = classify_conflict_state(
        projected_signals=mock_signals,
        country=scenario.primary_actor,
        sre_domains=None,
        trajectory_prob_up=0.0,
        prior_override=current_prior,
        transition_override=current_matrix,
    )

    # ── 5. Adaptive learning (in-memory only) ─────────────────────
    update_transition_matrix(
        previous_state=prev_state,
        actual_state=result.state,
        matrix=current_matrix,
    )

    # ── 6. Record matrix row AFTER update ─────────────────────────
    row_after = current_matrix[current_state_idx][:]
    delta = _matrix_row_delta(row_before, row_after)

    # ── 7. Count signal gaps ──────────────────────────────────────
    gaps = _count_signal_gaps(result.observed_groups)

    # ── 8. Build snapshot ─────────────────────────────────────────
    snap = DaySnapshot(
        date=date,
        conflict_state=result.state,
        conflict_posterior=dict(result.posterior),
        conflict_confidence=result.confidence,
        forecast_14d=dict(result.forecast_14d),
        p_active_or_higher_14d=result.p_active_or_higher_14d,
        ground_truth_state=gt_state,
        transition_matrix_row=row_after,
        learning_delta=delta,
        gap_count=gaps,
        observed_groups=dict(result.observed_groups),
        # Legacy fields — set p(up) from conflict posterior for compat
        prob_up=result.posterior.get("ACTIVE_CONFLICT", 0.0)
              + result.posterior.get("FULL_WAR", 0.0),
    )

    # ── 9. Structured log ─────────────────────────────────────────
    log.info(
        "[BACKTEST][Day %s] state=%s (gt=%s) conf=%.3f "
        "P(CRISIS)=%.3f P(ACTIVE)=%.3f P(ACTIVE+14d)=%.3f "
        "T_row=[%s] gaps=%d",
        date,
        result.state,
        gt_state,
        result.confidence,
        result.posterior.get("CRISIS", 0.0),
        result.posterior.get("ACTIVE_CONFLICT", 0.0),
        result.p_active_or_higher_14d,
        ",".join(f"{v:.3f}" for v in row_after),
        gaps,
    )

    return snap


# ══════════════════════════════════════════════════════════════════════
#  PUBLIC API — Scenario Replay
# ══════════════════════════════════════════════════════════════════════

def replay_scenario(
    scenario: BacktestScenario,
    enable_learning: bool = True,
    window_size: int = 1,
) -> ReplayResult:
    """
    Run the full replay for a BacktestScenario.

    Per-scenario isolation:
    - deepcopy of expert baseline transition matrix
    - Uniform prior (no prior carryover)
    - BACKTEST_MODE = True (no disk writes)
    - Matrix reset after simulation (no contamination)

    Parameters
    ----------
    scenario : BacktestScenario
        The scenario to replay.
    enable_learning : bool
        If True, adaptive learning updates the in-memory matrix each
        day.  If False, the matrix stays fixed at expert baseline.
    window_size : int
        Sliding window size for signal aggregation (default 1 = daily).
        Use 3 for 3-day rolling window — averages signals from
        window_size consecutive days for smoother, more stable
        predictions that match regime-level state changes.

    Returns
    -------
    ReplayResult with day-by-day snapshots and matrix comparison.
    """
    log.info("[Replay] ═══ Starting scenario: %s ═══", scenario.name)
    log.info("[Replay] Window: %s → %s", scenario.start_date, scenario.end_date)
    log.info("[Replay] Actors: %s | Region: %s", scenario.actors, scenario.region)
    log.info("[Replay] Signal source: %s", scenario.signal_source)
    log.info("[Replay] Learning: %s", "ENABLED" if enable_learning else "DISABLED")
    log.info("[Replay] Window size: %d", window_size)

    # ── 1. Snapshot expert baseline ───────────────────────────────
    scenario_matrix = copy.deepcopy(_EXPERT_TRANSITION)
    matrix_before = copy.deepcopy(scenario_matrix)

    # ── 2. Uniform prior ──────────────────────────────────────────
    current_prior = {s: 1.0 / _N for s in STATES}
    prev_state = "PEACE"  # default start state

    # ── 3. Activate backtest mode ─────────────────────────────────
    prev_backtest = os.environ.get("BACKTEST_MODE", "false")
    _set_backtest_mode(True)

    result = ReplayResult(
        crisis_name=scenario.name,
        scenario_name=scenario.name,
        start=scenario.start_date,
        escalation_peak=scenario.escalation_peak or scenario.end_date,
        ground_truth_phases=[
            {
                "start_date": p.start_date,
                "end_date": p.end_date,
                "ground_truth_state": p.ground_truth_state,
            }
            for p in scenario.phases
        ],
        matrix_before=matrix_before,
    )

    try:
        dates = date_range(scenario.start_date, scenario.end_date)
        log.info("[Replay] %d days to simulate", len(dates))

        for day_idx, date in enumerate(dates):
            # Pin temporal clock
            from Config.runtime_clock import frozen_date

            # 3-day sliding window signal aggregation
            if window_size > 1:
                w_start = max(0, day_idx - window_size + 1)
                window_dates = dates[w_start:day_idx + 1]
                agg = _aggregate_window_signals(
                    window_dates, scenario, day_idx
                )
                override = build_mock_signals(agg)
            else:
                override = None

            with frozen_date(date):
                snap = _simulate_day(
                    date=date,
                    scenario=scenario,
                    current_prior=current_prior,
                    current_matrix=scenario_matrix,
                    prev_state=prev_state,
                    day_index=day_idx,
                    mock_signals_override=override,
                )

            result.snapshots.append(snap)

            # Advance state for next day
            current_prior = dict(snap.conflict_posterior)
            prev_state = snap.conflict_state

            # If learning is disabled, reset matrix each day
            if not enable_learning:
                scenario_matrix = copy.deepcopy(_EXPERT_TRANSITION)

        result.matrix_after = copy.deepcopy(scenario_matrix)

        log.info("[Replay] ═══ Completed: %d snapshots ═══", result.days_count)
        log.info("[Replay] Peak P(ACTIVE+): %.4f", result.peak_p_active)

        # ── Persist replay results (diagnostic, always) ──────────
        _persist_replay_results(result)

    except Exception as exc:
        result.error = str(exc)
        log.error("[Replay] Error during backtest: %s", exc, exc_info=True)

    finally:
        # ── 4. Restore backtest mode ──────────────────────────────
        os.environ["BACKTEST_MODE"] = prev_backtest

    return result


def replay_all_scenarios(
    scenarios: Optional[List[BacktestScenario]] = None,
    enable_learning: bool = True,
    window_size: int = 1,
) -> List[ReplayResult]:
    """
    Run replay for all scenarios in the registry (or a supplied list).

    Parameters
    ----------
    scenarios : list, optional
        If None, uses the full SCENARIOS registry.
    enable_learning : bool
        Passed through to each ``replay_scenario()`` call.

    Returns
    -------
    List of ReplayResult objects (one per scenario).
    """
    if scenarios is None:
        from engine.Layer6_Backtesting.scenario_registry import SCENARIOS
        scenarios = SCENARIOS

    results: List[ReplayResult] = []
    for scenario in scenarios:
        r = replay_scenario(scenario, enable_learning=enable_learning, window_size=window_size)
        results.append(r)
        log.info(
            "[Replay] ── %s: %d days, error=%s",
            scenario.name, r.days_count, r.error,
        )

    log.info("[Replay] All %d scenarios complete.", len(results))
    return results


# ══════════════════════════════════════════════════════════════════════
#  BACKWARD-COMPATIBLE API (wraps old CrisisWindow interface)
# ══════════════════════════════════════════════════════════════════════

def _date_range(start_iso: str, end_iso: str) -> List[str]:
    """Generate list of ISO date strings from start to end inclusive."""
    return date_range(start_iso, end_iso)


def replay_crisis(crisis: CrisisWindow) -> ReplayResult:
    """
    Backward-compatible: replay a CrisisWindow.

    If a matching BacktestScenario exists in the registry, uses the
    full-spectrum engine.  Otherwise falls back to a minimal replay
    with CRISIS ground truth across the whole window.
    """
    # Try to find a matching scenario
    try:
        from engine.Layer6_Backtesting.scenario_registry import get_scenario
        scenario = get_scenario(crisis.name)
        return replay_scenario(scenario)
    except (KeyError, ImportError):
        pass

    # Fallback: construct a minimal scenario from CrisisWindow
    log.info("[Replay] Fallback: constructing minimal scenario from CrisisWindow")
    phases = [
        StatePhase(crisis.start, crisis.escalation_peak, "CRISIS"),
    ]
    scenario = BacktestScenario(
        name=crisis.name,
        actors=crisis.actors,
        region=crisis.region,
        description=crisis.description,
        phases=phases,
    )
    return replay_scenario(scenario)


def replay_all(crises: Optional[List[CrisisWindow]] = None) -> List[ReplayResult]:
    """
    Backward-compatible: replay all crises.

    Delegates to ``replay_all_scenarios()`` when possible.
    """
    if crises is None:
        return replay_all_scenarios()

    return [replay_crisis(c) for c in crises]


# ══════════════════════════════════════════════════════════════════════
#  DIAGNOSTIC PERSISTENCE
# ══════════════════════════════════════════════════════════════════════

_BACKTEST_DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "backtesting"
)


def _persist_replay_results(result: ReplayResult) -> None:
    """
    Write replay results to a JSONL file for offline analysis.

    One JSONL file per scenario under ``data/backtesting/``.
    These are diagnostic artifacts — NOT production model state —
    and are always written regardless of BACKTEST_MODE.
    """
    try:
        os.makedirs(_BACKTEST_DATA_DIR, exist_ok=True)
        safe_name = result.scenario_name.replace(" ", "_").lower()
        path = os.path.join(_BACKTEST_DATA_DIR, f"{safe_name}_replay.jsonl")
        with open(path, "w") as f:
            for snap in result.snapshots:
                f.write(json.dumps(snap.to_dict()) + "\n")
        log.info("[Replay] Persisted %d snapshots to %s", len(result.snapshots), path)
    except Exception as exc:
        log.warning("[Replay] Failed to persist results: %s", exc)
