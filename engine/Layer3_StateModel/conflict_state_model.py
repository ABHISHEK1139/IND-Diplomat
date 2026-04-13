"""
Layer3_StateModel/conflict_state_model.py
=========================================
Bayesian Conflict-State Model with Adaptive Transition Matrix.

Architecture
------------
Three layers, cleanly separated:

1. **Likelihood Model** — Gaussian distance from state signal profiles.
   No thresholds.  Just probability.

2. **Transition Matrix** — Encodes state inertia.  War has inertia.
   Peace has inertia.  Prevents instant flipping.

3. **Adaptive Learning** — When outcomes resolve, transition weights
   update via bounded gradient.  Over time the matrix becomes empirical.

Core Equation
-------------
Each run:

    P_new(state_i) = normalise(
        sum_j [ P_old(state_j) * T(j -> i) ] * L(observations | state_i)
    )

Integration Rule
----------------
Conflict state = position  (What is happening NOW?)
SRE            = velocity  (Is it intensifying?)

They are parallel axes.  **Never mix them.**

Persistence
-----------
- Prior state probabilities stored per-country in
  ``data/state_history/conflict_prior_{ISO3}.json``
- Adaptive transition matrix stored in
  ``data/state_history/transition_matrix.json``
- Full history appended to
  ``data/state_history/conflict_state_history.jsonl``

Author: IND-DIPLOMAT system  |  Phase: Conflict State Layer (v2 — Bayesian)
"""

from __future__ import annotations

import copy
import json
import logging
import math
import os
import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Layer3.conflict_state")


def _backtest_mode() -> bool:
    """Check if backtesting isolation is active (lazy import to avoid circular)."""
    try:
        from Config.config import BACKTEST_MODE
        return BACKTEST_MODE
    except Exception:
        return os.getenv("BACKTEST_MODE", "false").lower() == "true"

# ══════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════

STATES: Tuple[str, ...] = (
    "PEACE",
    "CRISIS",
    "LIMITED_STRIKES",
    "ACTIVE_CONFLICT",
    "FULL_WAR",
)
_N = len(STATES)
_STATE_IDX = {s: i for i, s in enumerate(STATES)}

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "state_history")

# ══════════════════════════════════════════════════════════════════════
#  1.  STATE SIGNAL PROFILES  (Expected signal values per state)
# ══════════════════════════════════════════════════════════════════════
# Keys are normalised signal groups (not raw signal names).
# Values are the expected confidence [0-1] for that group in each state.

STATE_PROFILES: Dict[str, Dict[str, float]] = {
    "PEACE": {
        "mil_escalation":   0.05,
        "mobilization":     0.05,
        "force_posture":    0.08,
        "logistics":        0.03,
        "hostility":        0.10,
        "wmd_risk":         0.03,
        "instability":      0.10,
        "diplomacy_active": 0.60,
        "coercive":         0.05,
        "alliance":         0.10,
        "cyber":            0.05,
        "economic_pressure":0.10,
    },
    "CRISIS": {
        "mil_escalation":   0.25,
        "mobilization":     0.15,
        "force_posture":    0.30,
        "logistics":        0.10,
        "hostility":        0.45,
        "wmd_risk":         0.15,
        "instability":      0.30,
        "diplomacy_active": 0.40,
        "coercive":         0.35,
        "alliance":         0.25,
        "cyber":            0.20,
        "economic_pressure":0.30,
    },
    "LIMITED_STRIKES": {
        "mil_escalation":   0.50,
        "mobilization":     0.30,
        "force_posture":    0.55,
        "logistics":        0.35,
        "hostility":        0.55,
        "wmd_risk":         0.30,
        "instability":      0.35,
        "diplomacy_active": 0.25,
        "coercive":         0.50,
        "alliance":         0.40,
        "cyber":            0.35,
        "economic_pressure":0.40,
    },
    "ACTIVE_CONFLICT": {
        "mil_escalation":   0.75,
        "mobilization":     0.65,
        "force_posture":    0.80,
        "logistics":        0.65,
        "hostility":        0.65,
        "wmd_risk":         0.45,
        "instability":      0.50,
        "diplomacy_active": 0.15,
        "coercive":         0.55,
        "alliance":         0.55,
        "cyber":            0.50,
        "economic_pressure":0.55,
    },
    "FULL_WAR": {
        "mil_escalation":   0.92,
        "mobilization":     0.88,
        "force_posture":    0.95,
        "logistics":        0.85,
        "hostility":        0.75,
        "wmd_risk":         0.60,
        "instability":      0.60,
        "diplomacy_active": 0.05,
        "coercive":         0.60,
        "alliance":         0.65,
        "cyber":            0.60,
        "economic_pressure":0.65,
    },
}

# ── Signal name → profile group mapping ────────────────────────────
# Imported from unified signal_registry + extended with aliases
# so that legacy callers still work.
try:
    from engine.Layer3_StateModel.signal_registry import (
        SIGNAL_TO_GROUP as _REGISTRY_GROUPS,
        ALIAS_TO_CANONICAL as _REGISTRY_ALIASES,
        canonicalize as _canonicalize,
    )
    # Build combined mapping: canonical + alias → group
    _SIGNAL_TO_GROUP: Dict[str, str] = dict(_REGISTRY_GROUPS)
    for _alias, _canon in _REGISTRY_ALIASES.items():
        if _alias not in _SIGNAL_TO_GROUP and _canon in _REGISTRY_GROUPS:
            _SIGNAL_TO_GROUP[_alias] = _REGISTRY_GROUPS[_canon]
except ImportError:
    _canonicalize = lambda t: t  # noqa: E731
    _SIGNAL_TO_GROUP: Dict[str, str] = {
        "SIG_MIL_ESCALATION": "mil_escalation",
        "SIG_MIL_MOBILIZATION": "mobilization",
        "SIG_FORCE_POSTURE": "force_posture",
        "SIG_LOGISTICS_PREP": "logistics",
        "SIG_DIP_HOSTILITY": "hostility",
        "SIG_COERCIVE_BARGAINING": "coercive",
        "SIG_DIPLOMACY_ACTIVE": "diplomacy_active",
        "SIG_ALLIANCE_ACTIVATION": "alliance",
        "SIG_ECONOMIC_PRESSURE": "economic_pressure",
        "SIG_CYBER_ACTIVITY": "cyber",
        "SIG_INTERNAL_INSTABILITY": "instability",
        "SIG_DECEPTION_ACTIVITY": "coercive",
        "SIG_KINETIC_ACTIVITY": "mil_escalation",
    }


# ══════════════════════════════════════════════════════════════════════
#  2.  TRANSITION MATRIX  (Expert prior — rows sum to 1)
# ══════════════════════════════════════════════════════════════════════
# T[i][j] = P(next=j | current=i).
# War states are sticky.  Adjacent transitions allowed.
# No skip-jumps (PEACE → ACTIVE_CONFLICT direct has 0 probability).

_EXPERT_TRANSITION: List[List[float]] = [
    # TO ->  PEACE  CRISIS  LIMITED  ACTIVE  FULL
    [0.85,   0.15,   0.00,    0.00,   0.00],   # FROM PEACE
    [0.10,   0.70,   0.20,    0.00,   0.00],   # FROM CRISIS
    [0.00,   0.10,   0.60,    0.30,   0.00],   # FROM LIMITED_STRIKES
    [0.00,   0.00,   0.15,    0.70,   0.15],   # FROM ACTIVE_CONFLICT
    [0.00,   0.00,   0.00,    0.20,   0.80],   # FROM FULL_WAR
]

# ── Sigma for Gaussian likelihood ──────────────────────────────────
# Fix 3: Adaptive sigma per signal group.  Groups with wide inter-state
# variance (e.g. mil_escalation: PEACE=0.05 → FULL_WAR=0.92, spread=0.87)
# get TIGHTER sigma for better differentiation.  Groups with narrow
# spread (e.g. instability: 0.10 → 0.60, spread=0.50) get wider sigma.
#
# Formula: σ = 0.12 + 0.10 × (1 - spread)
#   High spread (0.87) → σ ≈ 0.13  (tight — very discriminating)
#   Low spread  (0.50) → σ ≈ 0.17  (wider — less discriminating)
#
# This replaces the global σ=0.30 that couldn't differentiate states.
_SIGMA = 0.18  # fallback for unknown groups (tighter than 0.30)

def _compute_group_sigmas() -> Dict[str, float]:
    """Pre-compute adaptive sigma for each profile group."""
    sigmas: Dict[str, float] = {}
    groups = set()
    for profile in STATE_PROFILES.values():
        groups.update(profile.keys())
    for group in groups:
        values = [STATE_PROFILES[s].get(group, 0.0) for s in STATES]
        spread = max(values) - min(values)
        # Tighter sigma for high-spread groups, wider for low-spread
        sigmas[group] = 0.12 + 0.10 * (1.0 - spread)
    return sigmas

_GROUP_SIGMA: Dict[str, float] = _compute_group_sigmas()

# ── Adaptive learning rate ─────────────────────────────────────────
_LEARNING_RATE = 0.01
_MIN_TRANSITION_PROB = 0.001   # floor — prevent zeros
_MAX_TRANSITION_PROB = 0.95    # ceiling — prevent certainty


# ══════════════════════════════════════════════════════════════════════
#  3.  PERSISTENCE
# ══════════════════════════════════════════════════════════════════════

def _ensure_data_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)


def _load_prior(country: str) -> Dict[str, float]:
    """Load last posterior as this run's prior.  Uniform if first run."""
    _ensure_data_dir()
    path = os.path.join(_DATA_DIR, f"conflict_prior_{country}.json")
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
            # Validate
            if isinstance(data, dict) and all(s in data for s in STATES):
                total = sum(data.values())
                if total > 0:
                    return {s: data[s] / total for s in STATES}
    except Exception as exc:
        logger.warning("[CONFLICT-STATE] Failed to load prior for %s: %s", country, exc)
    # Default equal prior
    return {s: 1.0 / _N for s in STATES}


def _save_prior(country: str, posterior: Dict[str, float]):
    """Persist posterior for next run.  No-op when BACKTEST_MODE is active."""
    if _backtest_mode():
        return
    _ensure_data_dir()
    path = os.path.join(_DATA_DIR, f"conflict_prior_{country}.json")
    try:
        with open(path, "w") as f:
            json.dump({s: round(posterior[s], 6) for s in STATES}, f, indent=2)
    except Exception as exc:
        logger.warning("[CONFLICT-STATE] Failed to save prior for %s: %s", country, exc)


def _load_transition_matrix() -> List[List[float]]:
    """Load adaptive transition matrix.  Expert prior if none stored."""
    _ensure_data_dir()
    path = os.path.join(_DATA_DIR, "transition_matrix.json")
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) == _N:
                return data
    except Exception as exc:
        logger.warning("[CONFLICT-STATE] Failed to load transition matrix: %s", exc)
    return [row[:] for row in _EXPERT_TRANSITION]


def _save_transition_matrix(matrix: List[List[float]]):
    """Persist adaptive transition matrix.  No-op when BACKTEST_MODE is active."""
    if _backtest_mode():
        return
    _ensure_data_dir()
    path = os.path.join(_DATA_DIR, "transition_matrix.json")
    try:
        with open(path, "w") as f:
            json.dump([[round(v, 6) for v in row] for row in matrix], f, indent=2)
    except Exception as exc:
        logger.warning("[CONFLICT-STATE] Failed to save transition matrix: %s", exc)


def _append_history(record: Dict[str, Any]):
    """Append state classification to JSONL history.  No-op when BACKTEST_MODE."""
    if _backtest_mode():
        return
    _ensure_data_dir()
    path = os.path.join(_DATA_DIR, "conflict_state_history.jsonl")
    try:
        with open(path, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════
#  4.  LIKELIHOOD COMPUTATION
# ══════════════════════════════════════════════════════════════════════

def _gaussian_likelihood(observed: float, expected: float, sigma: float = _SIGMA) -> float:
    """Gaussian likelihood: how well does observed match expected?"""
    return math.exp(-((observed - expected) ** 2) / (2.0 * sigma ** 2))


# Likelihood floor: absence of evidence != evidence of absence.
# Prevents zero-likelihood from freezing Bayesian state transitions.
_LIKELIHOOD_FLOOR: float = 0.05


def _compute_likelihood(observed_groups: Dict[str, float]) -> Dict[str, float]:
    """
    Compute likelihood L(observations | state) for each state.

    Fix 3: Uses per-group adaptive sigma instead of global σ=0.30.
    Groups with high inter-state profile spread (like mil_escalation)
    use tighter sigma → actually differentiate states when observed
    values are low (e.g., observed=0.25 now clearly favors CRISIS
    over PEACE for military signals).

    Phase 8 fix preserved: Only compute over OBSERVED groups (>0.01).
    """
    _OBS_THRESHOLD = 0.01
    likelihoods: Dict[str, float] = {}

    for state in STATES:
        profile = STATE_PROFILES[state]
        log_l = 0.0
        n_observed = 0

        for group, expected in profile.items():
            observed = observed_groups.get(group, 0.0)
            if observed < _OBS_THRESHOLD:
                continue
            n_observed += 1
            # Use per-group adaptive sigma
            sigma = _GROUP_SIGMA.get(group, _SIGMA)
            gl = _gaussian_likelihood(observed, expected, sigma)
            log_l += math.log(max(gl, 1e-30))

        if n_observed == 0:
            likelihoods[state] = 1.0
        else:
            likelihoods[state] = max(_LIKELIHOOD_FLOOR, math.exp(log_l))

    return likelihoods


# ══════════════════════════════════════════════════════════════════════
#  5.  BAYESIAN UPDATE ENGINE
# ══════════════════════════════════════════════════════════════════════

def _bayesian_update(
    prior: Dict[str, float],
    transition: List[List[float]],
    likelihood: Dict[str, float],
) -> Dict[str, float]:
    """
    Full Bayesian update with transition matrix.

    P_new(i) = normalise( sum_j [ P_old(j) * T(j,i) ] * L(i) )
    """
    predicted = [0.0] * _N

    # Prediction step: apply transition matrix
    for i in range(_N):
        for j in range(_N):
            predicted[i] += prior[STATES[j]] * transition[j][i]

    # Update step: multiply by likelihood
    unnorm = [0.0] * _N
    for i in range(_N):
        unnorm[i] = predicted[i] * likelihood[STATES[i]]

    # Normalise
    total = sum(unnorm)
    if total < 1e-30:
        return {s: 1.0 / _N for s in STATES}  # fallback uniform

    return {STATES[i]: unnorm[i] / total for i in range(_N)}


# ══════════════════════════════════════════════════════════════════════
#  6.  ADAPTIVE LEARNING
# ══════════════════════════════════════════════════════════════════════

def update_transition_matrix(
    previous_state: str,
    actual_state: str,
    learning_rate: float = _LEARNING_RATE,
    matrix: Optional[List[List[float]]] = None,
) -> List[List[float]]:
    """
    Update transition matrix based on observed state transition.

    Reinforces T[prev][actual], weakens other T[prev][*].
    Bounded by min/max to prevent degenerate matrices.

    Parameters
    ----------
    previous_state : str
        State from previous run
    actual_state : str
        State from current run (the observed transition)
    learning_rate : float
        Step size for update
    matrix : list[list[float]], optional
        If provided, update this matrix **in-place** and return it
        (no disk I/O).  Used by the replay engine for per-scenario
        isolation.  When ``None``, loads from disk (production path).

    Returns
    -------
    Updated transition matrix
    """
    in_memory = matrix is not None
    if previous_state not in _STATE_IDX or actual_state not in _STATE_IDX:
        return matrix if in_memory else _load_transition_matrix()

    if not in_memory:
        matrix = _load_transition_matrix()

    i = _STATE_IDX[previous_state]
    j_actual = _STATE_IDX[actual_state]

    row = matrix[i]

    # Reinforce actual transition, weaken others
    for j in range(_N):
        if j == j_actual:
            row[j] = min(row[j] + learning_rate, _MAX_TRANSITION_PROB)
        else:
            row[j] = max(row[j] - learning_rate / (_N - 1), _MIN_TRANSITION_PROB)

    # Re-normalise row to sum to 1
    row_sum = sum(row)
    matrix[i] = [v / row_sum for v in row]

    if not in_memory:
        _save_transition_matrix(matrix)
    logger.info(
        "[CONFLICT-STATE] Transition matrix updated: %s -> %s (lr=%.3f)%s",
        previous_state, actual_state, learning_rate,
        " [in-memory]" if in_memory else "",
    )
    return matrix


# ══════════════════════════════════════════════════════════════════════
#  7.  14-DAY STATE TRANSITION FORECAST
# ══════════════════════════════════════════════════════════════════════

def _forecast_transition(
    posterior: Dict[str, float],
    transition: List[List[float]],
    steps: int = 14,
    trajectory_prob_up: float = 0.0,
) -> Dict[str, float]:
    """
    Monte Carlo-free forecast: iterate transition matrix `steps` times
    from current posterior to estimate state distribution in `steps` days.

    Parameters
    ----------
    posterior : dict
        Current state distribution.
    transition : list[list[float]]
        Base transition matrix.
    steps : int
        Number of forward steps (days).
    trajectory_prob_up : float
        P(HIGH in 14d) from trajectory model.  If > 0.70, boosts
        CRISIS → ACTIVE_CONFLICT transition by +5% (trajectory → state
        coupling) and re-normalises the row.

    Returns probability distribution over states at t+steps.
    """
    # Copy transition so we don't mutate the original
    t = [row[:] for row in transition]

    # ── Trajectory → State coupling ──────────────────────────────
    # When trajectory model shows strong escalation probability,
    # make the CRISIS → ACTIVE_CONFLICT path more likely.
    if trajectory_prob_up > 0.70:
        crisis_idx = STATES.index("CRISIS")
        active_idx = STATES.index("ACTIVE_CONFLICT")
        boost = 0.05
        t[crisis_idx][active_idx] += boost
        # Re-normalise the CRISIS row
        row_sum = sum(t[crisis_idx])
        if row_sum > 0:
            t[crisis_idx] = [v / row_sum for v in t[crisis_idx]]
        logger.info(
            "[CONFLICT-STATE] Trajectory→State coupling: prob_up=%.3f > 0.70 "
            "→ CRISIS→ACTIVE +5%%",
            trajectory_prob_up,
        )

    current = [posterior[s] for s in STATES]

    for _ in range(steps):
        next_state = [0.0] * _N
        for i in range(_N):
            for j in range(_N):
                next_state[i] += current[j] * t[j][i]
        current = next_state

    total = sum(current)
    if total < 1e-30:
        return {s: 1.0 / _N for s in STATES}

    return {STATES[i]: current[i] / total for i in range(_N)}


# ══════════════════════════════════════════════════════════════════════
#  8.  RESULT DATA CLASS
# ══════════════════════════════════════════════════════════════════════

@dataclass
class ConflictStateResult:
    """Full result of Bayesian conflict state classification."""
    state: str                                              # MAP state
    confidence: float                                       # posterior of MAP state
    posterior: Dict[str, float] = field(default_factory=dict)
    prior_used: Dict[str, float] = field(default_factory=dict)
    likelihood: Dict[str, float] = field(default_factory=dict)
    observed_groups: Dict[str, float] = field(default_factory=dict)
    forecast_14d: Dict[str, float] = field(default_factory=dict)
    p_active_or_higher_14d: float = 0.0
    transition_source: str = "expert"                       # "expert" or "adaptive"
    country: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "confidence": round(self.confidence, 4),
            "posterior": {k: round(v, 4) for k, v in self.posterior.items()},
            "prior_used": {k: round(v, 4) for k, v in self.prior_used.items()},
            "likelihood": {k: round(v, 6) for k, v in self.likelihood.items()},
            "observed_groups": {k: round(v, 4) for k, v in self.observed_groups.items()},
            "forecast_14d": {k: round(v, 4) for k, v in self.forecast_14d.items()},
            "p_active_or_higher_14d": round(self.p_active_or_higher_14d, 4),
            "transition_source": self.transition_source,
            "country": self.country,
        }


# ══════════════════════════════════════════════════════════════════════
#  9.  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

def classify_conflict_state(
    projected_signals: Dict[str, Any],
    country: str = "",
    sre_domains: Optional[Dict[str, float]] = None,
    trajectory_prob_up: float = 0.0,
    prior_override: Optional[Dict[str, float]] = None,
    transition_override: Optional[List[List[float]]] = None,
) -> ConflictStateResult:
    """
    Bayesian conflict state classification with adaptive transition matrix.

    Parameters
    ----------
    projected_signals : dict
        Signal name -> signal object (must have .confidence attribute).
    country : str
        ISO-3 country code (for prior persistence).
    sre_domains : dict, optional
        Domain indices — NOT used for classification (parallel axis rule),
        but logged for diagnostics.
    trajectory_prob_up : float
        P(HIGH in 14 days) from the previous cycle's trajectory model.
        If > 0.70, boosts CRISIS → ACTIVE_CONFLICT transition rate by 5%%
        in the 14-day forecast (trajectory → state coupling).
    prior_override : dict, optional
        If provided, use this as the prior instead of loading from disk.
        Used by the replay engine for per-scenario temporal isolation.
    transition_override : list[list[float]], optional
        If provided, use this transition matrix instead of loading from
        disk.  Used by the replay engine for per-scenario matrix isolation.

    Returns
    -------
    ConflictStateResult
    """
    country = (country or "").upper().strip()

    # ── Step 1: Extract signal confidences and map to groups ───────
    sig_conf: Dict[str, float] = {}
    for name, sig in (projected_signals or {}).items():
        conf = float(getattr(sig, "confidence", 0.0) or 0.0)
        if conf > 0.0:
            sig_conf[name] = conf

    # Aggregate by group (take max confidence per group)
    observed_groups: Dict[str, float] = {}
    for sig_name, confidence in sig_conf.items():
        group = _SIGNAL_TO_GROUP.get(sig_name)
        if group:
            observed_groups[group] = max(observed_groups.get(group, 0.0), confidence)

    logger.info(
        "[CONFLICT-STATE] Observed signal groups: %s",
        " ".join(f"{g}={v:.3f}" for g, v in sorted(observed_groups.items())),
    )

    # ── Step 2: Load prior (last posterior, or uniform) ────────────
    if prior_override is not None:
        prior = prior_override
    else:
        prior = _load_prior(country)
    logger.info(
        "[CONFLICT-STATE] Prior: %s",
        " ".join(f"{s}={prior[s]:.3f}" for s in STATES),
    )

    # ── Step 3: Load transition matrix ─────────────────────────────
    if transition_override is not None:
        transition = transition_override
        t_source = "override"
    else:
        transition = _load_transition_matrix()
        # Determine if adaptive or expert
        t_path = os.path.join(_DATA_DIR, "transition_matrix.json")
        t_source = "adaptive" if os.path.exists(t_path) else "expert"

    # ── Step 4: Compute likelihood ─────────────────────────────────
    likelihood = _compute_likelihood(observed_groups)
    logger.info(
        "[CONFLICT-STATE] Likelihood: %s",
        " ".join(f"{s}={likelihood[s]:.6f}" for s in STATES),
    )

    # ── Step 5: Bayesian update ────────────────────────────────────
    posterior = _bayesian_update(prior, transition, likelihood)
    logger.info(
        "[CONFLICT-STATE] Posterior: %s",
        " ".join(f"{s}={posterior[s]:.3f}" for s in STATES),
    )

    # ── Step 6: MAP state ──────────────────────────────────────────
    map_state = max(STATES, key=lambda s: posterior[s])
    map_conf = posterior[map_state]

    # ── Step 7: Adaptive transition learning ───────────────────────
    # Compare previous prior's MAP to current MAP
    prior_map = max(STATES, key=lambda s: prior[s])
    if prior_map != map_state or True:  # always update for learning
        update_transition_matrix(prior_map, map_state)

    # ── Step 8: Save posterior as next run's prior ─────────────────
    _save_prior(country, posterior)

    # ── Step 9: 14-day forecast ────────────────────────────────────
    forecast_14d = _forecast_transition(
        posterior, transition, steps=14,
        trajectory_prob_up=trajectory_prob_up,
    )
    p_active_or_higher = (
        forecast_14d.get("ACTIVE_CONFLICT", 0.0) +
        forecast_14d.get("FULL_WAR", 0.0)
    )

    logger.info(
        "[CONFLICT-STATE] Forecast 14d: %s | P(ACTIVE+)=%.3f",
        " ".join(f"{s}={forecast_14d[s]:.3f}" for s in STATES),
        p_active_or_higher,
    )

    # ── Step 10: Build result ──────────────────────────────────────
    result = ConflictStateResult(
        state=map_state,
        confidence=map_conf,
        posterior=posterior,
        prior_used=prior,
        likelihood=likelihood,
        observed_groups=observed_groups,
        forecast_14d=forecast_14d,
        p_active_or_higher_14d=p_active_or_higher,
        transition_source=t_source,
        country=country,
    )

    # ── Step 11: Append to history ─────────────────────────────────
    _append_history({
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "country": country,
        "state": map_state,
        "confidence": round(map_conf, 4),
        "posterior": {s: round(posterior[s], 4) for s in STATES},
        "observed_groups": {k: round(v, 4) for k, v in observed_groups.items()},
        "p_active_14d": round(p_active_or_higher, 4),
        "transition_source": t_source,
    })

    logger.info(
        "[CONFLICT-STATE] RESULT: %s (%.1f%%) | 14d P(ACTIVE+)=%.1f%% | matrix=%s",
        map_state, map_conf * 100, p_active_or_higher * 100, t_source,
    )

    return result
