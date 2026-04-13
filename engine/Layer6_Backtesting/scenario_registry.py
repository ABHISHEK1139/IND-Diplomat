"""
Layer6_Backtesting — Scenario Registry
========================================

Expert-annotated historical scenarios for full-spectrum backtesting.

Each scenario defines:
    - Crisis metadata (name, actors, region)
    - Per-date-range **ground truth conflict state** labels
    - Signal source mode (synthetic, file, or gdelt)

Ground truth phases are expert-annotated based on publicly documented
historical events.  These labels provide the reference against which
the Bayesian conflict state model is evaluated.

The 5 conflict states:
    PEACE → CRISIS → LIMITED_STRIKES → ACTIVE_CONFLICT → FULL_WAR

Phase 6 — Full-Spectrum Backtesting.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from engine.Layer3_StateModel.conflict_state_model import (
    STATES,
    STATE_PROFILES,
    _N,
)


# ══════════════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════

@dataclass
class StatePhase:
    """A contiguous date range during which the ground truth state is fixed."""
    start_date: str              # ISO YYYY-MM-DD
    end_date: str                # ISO YYYY-MM-DD  (inclusive)
    ground_truth_state: str      # one of STATES

    def __post_init__(self):
        if self.ground_truth_state not in STATES:
            raise ValueError(
                f"Invalid ground truth state '{self.ground_truth_state}'. "
                f"Must be one of {STATES}"
            )


@dataclass
class BacktestScenario:
    """
    A historical scenario with expert-annotated ground truth timeline.

    The ``phases`` list must cover the entire date range from the first
    phase's start_date through the last phase's end_date, with no gaps
    or overlaps.  The replay engine will iterate day-by-day through
    this range, using synthetic (or file-based) signals and comparing
    the Bayesian classifier's output against the annotated state.
    """
    name: str
    actors: List[str] = field(default_factory=list)
    region: str = ""
    description: str = ""
    phases: List[StatePhase] = field(default_factory=list)
    signal_source: str = "synthetic"     # "synthetic" | "file" | "gdelt"
    signal_data_path: Optional[str] = None

    @property
    def start_date(self) -> str:
        return self.phases[0].start_date if self.phases else ""

    @property
    def end_date(self) -> str:
        return self.phases[-1].end_date if self.phases else ""

    @property
    def primary_actor(self) -> str:
        """First actor code — used as the country for conflict model."""
        return self.actors[0] if self.actors else "UNK"

    @property
    def escalation_peak(self) -> Optional[str]:
        """First date of ACTIVE_CONFLICT or FULL_WAR, if any."""
        for phase in self.phases:
            if phase.ground_truth_state in ("ACTIVE_CONFLICT", "FULL_WAR"):
                return phase.start_date
        return None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "actors": self.actors,
            "region": self.region,
            "description": self.description,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "escalation_peak": self.escalation_peak,
            "signal_source": self.signal_source,
            "phases": [
                {
                    "start_date": p.start_date,
                    "end_date": p.end_date,
                    "ground_truth_state": p.ground_truth_state,
                }
                for p in self.phases
            ],
        }


# ══════════════════════════════════════════════════════════════════════
#  GROUND TRUTH HELPERS
# ══════════════════════════════════════════════════════════════════════

def get_ground_truth(scenario: BacktestScenario, date: str) -> str:
    """
    Return the expert-annotated ground truth state for a specific date.

    Parameters
    ----------
    scenario : BacktestScenario
    date : str
        ISO YYYY-MM-DD

    Returns
    -------
    str — one of STATES

    Raises
    ------
    ValueError if date falls outside all phases
    """
    for phase in scenario.phases:
        if phase.start_date <= date <= phase.end_date:
            return phase.ground_truth_state
    raise ValueError(
        f"Date {date} falls outside all phases of scenario '{scenario.name}'"
    )


def get_one_hot(state: str) -> Dict[str, float]:
    """
    Return one-hot vector over the 5 conflict states.

    >>> get_one_hot("CRISIS")
    {'PEACE': 0.0, 'CRISIS': 1.0, 'LIMITED_STRIKES': 0.0,
     'ACTIVE_CONFLICT': 0.0, 'FULL_WAR': 0.0}
    """
    return {s: (1.0 if s == state else 0.0) for s in STATES}


def date_range(start_iso: str, end_iso: str) -> List[str]:
    """Generate list of ISO date strings from start to end inclusive."""
    start = datetime.strptime(start_iso, "%Y-%m-%d")
    end = datetime.strptime(end_iso, "%Y-%m-%d")
    dates: List[str] = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates


# ══════════════════════════════════════════════════════════════════════
#  SYNTHETIC SIGNAL GENERATION
# ══════════════════════════════════════════════════════════════════════

def generate_synthetic_signals(
    ground_truth_state: str,
    noise_sigma: float = 0.08,
    seed: Optional[int] = None,
) -> Dict[str, float]:
    """
    Generate synthetic signal-group values from the state's profile.

    Uses the ``STATE_PROFILES`` baseline for the ground truth state,
    then adds Gaussian noise to simulate observation uncertainty.
    Values are clamped to [0, 1].

    Parameters
    ----------
    ground_truth_state : str
        The true conflict state for this day.
    noise_sigma : float
        Standard deviation of Gaussian noise added to each signal group.
    seed : int, optional
        RNG seed for reproducibility.

    Returns
    -------
    Dict[str, float]
        Signal group name → observed value (0-1).
    """
    if ground_truth_state not in STATE_PROFILES:
        raise ValueError(f"Unknown state: {ground_truth_state}")

    rng = random.Random(seed)
    profile = STATE_PROFILES[ground_truth_state]

    observed: Dict[str, float] = {}
    for group, expected in profile.items():
        noisy = expected + rng.gauss(0.0, noise_sigma)
        observed[group] = max(0.0, min(1.0, noisy))

    return observed


def _group_to_signal_name(group: str) -> str:
    """
    Map a signal group name back to a canonical signal name.

    The conflict state model maps signal names → groups via
    ``_SIGNAL_TO_GROUP``.  For synthetic replay we need the inverse.
    We use a canonical representative signal for each group.
    """
    _GROUP_TO_SIGNAL = {
        "mil_escalation":   "SIG_MIL_ESCALATION",
        "mobilization":     "SIG_MIL_MOBILIZATION",
        "force_posture":    "SIG_FORCE_POSTURE",
        "logistics":        "SIG_LOGISTICS_PREP",
        "hostility":        "SIG_DIP_HOSTILITY",
        "wmd_risk":         "SIG_WMD_RISK",
        "instability":      "SIG_INTERNAL_INSTABILITY",
        "diplomacy_active": "SIG_DIPLOMACY_ACTIVE",
        "coercive":         "SIG_COERCIVE_BARGAINING",
        "alliance":         "SIG_ALLIANCE_ACTIVATION",
        "cyber":            "SIG_CYBER_ACTIVITY",
        "economic_pressure":"SIG_ECON_PRESSURE",
    }
    return _GROUP_TO_SIGNAL.get(group, f"SIG_{group.upper()}")


class _MockSignal:
    """Minimal signal object with a .confidence attribute for the classifier."""
    __slots__ = ("confidence",)

    def __init__(self, confidence: float):
        self.confidence = confidence


def build_mock_signals(signal_groups: Dict[str, float]) -> Dict[str, object]:
    """
    Convert signal-group values to a dict of mock signal objects
    compatible with ``classify_conflict_state(projected_signals=...)``.

    Parameters
    ----------
    signal_groups : dict
        Signal group name → observed value (0-1).

    Returns
    -------
    dict
        Signal name → _MockSignal(confidence=value).
    """
    return {
        _group_to_signal_name(group): _MockSignal(confidence=val)
        for group, val in signal_groups.items()
    }


# ══════════════════════════════════════════════════════════════════════
#  SCENARIO REGISTRY — Expert-Annotated Historical Crises
# ══════════════════════════════════════════════════════════════════════
# Ground truth states are assigned based on publicly documented
# historical events and expert judgment.  Transition dates are
# approximate — selected to be within 1-3 days of the consensus
# scholarly and journalistic record.

SCENARIOS: List[BacktestScenario] = [
    # ── 1. Crimea Annexation (2014) ──────────────────────────────
    BacktestScenario(
        name="Crimea Annexation",
        actors=["RUS", "UKR"],
        region="Eastern Europe",
        description="Russian annexation of Crimea following Euromaidan revolution",
        phases=[
            StatePhase("2014-01-01", "2014-02-20", "PEACE"),
            StatePhase("2014-02-21", "2014-02-26", "CRISIS"),
            # Armed men seize parliament 2014-02-27
            StatePhase("2014-02-27", "2014-03-18", "LIMITED_STRIKES"),
        ],
    ),
    # ── 2. Ukraine Invasion (2022) ───────────────────────────────
    BacktestScenario(
        name="Ukraine Invasion",
        actors=["RUS", "UKR"],
        region="Eastern Europe",
        description="Full-scale Russian invasion following months of buildup",
        phases=[
            StatePhase("2021-10-01", "2021-11-14", "PEACE"),
            # Nov: satellite imagery of troop buildup
            StatePhase("2021-11-15", "2022-01-31", "CRISIS"),
            # Feb 1-23: Diplomatic breakdown, troop positioning
            StatePhase("2022-02-01", "2022-02-23", "CRISIS"),
            # Feb 24: Full-scale invasion
            StatePhase("2022-02-24", "2022-03-31", "ACTIVE_CONFLICT"),
        ],
    ),
    # ── 3. Israel-Hamas War (2023) ───────────────────────────────
    BacktestScenario(
        name="Israel-Hamas War",
        actors=["ISR", "PSE"],
        region="Middle East",
        description="Hamas attack on Israel triggering major conflict in Gaza",
        phases=[
            StatePhase("2023-09-01", "2023-10-06", "PEACE"),
            # Oct 7: Hamas attack — immediate escalation
            StatePhase("2023-10-07", "2023-10-12", "ACTIVE_CONFLICT"),
            # Oct 13+: Full-scale IDF ground operation planning
            StatePhase("2023-10-13", "2023-11-15", "ACTIVE_CONFLICT"),
        ],
    ),
    # ── 4. Iran-Saudi Tensions 2019 ──────────────────────────────
    BacktestScenario(
        name="Iran-Saudi Tensions 2019",
        actors=["IRN", "SAU"],
        region="Persian Gulf",
        description="Abqaiq-Khurais drone attacks on Saudi oil facilities",
        phases=[
            StatePhase("2019-08-01", "2019-09-13", "PEACE"),
            # Sep 14: Drone/cruise missile attack on Aramco
            StatePhase("2019-09-14", "2019-09-18", "LIMITED_STRIKES"),
            # Sep 19+: Standoff / de-escalation
            StatePhase("2019-09-19", "2019-10-15", "CRISIS"),
        ],
    ),
    # ── 5. Soleimani Assassination (2020) ────────────────────────
    BacktestScenario(
        name="Soleimani Assassination",
        actors=["IRN", "USA"],
        region="Persian Gulf",
        description="US assassination of Qasem Soleimani and subsequent escalation",
        phases=[
            StatePhase("2019-12-01", "2020-01-02", "PEACE"),
            # Jan 3: Soleimani killed by drone strike
            StatePhase("2020-01-03", "2020-01-07", "LIMITED_STRIKES"),
            # Jan 8: Iranian ballistic missile retaliation on Al Asad
            StatePhase("2020-01-08", "2020-01-10", "LIMITED_STRIKES"),
            # Jan 11+: De-escalation signaling
            StatePhase("2020-01-11", "2020-02-01", "CRISIS"),
        ],
    ),
    # ── 6. Strait of Hormuz Tanker Crisis (2019) ──────────────────
    BacktestScenario(
        name="Strait of Hormuz Tanker Crisis",
        actors=["IRN", "GBR", "USA"],
        region="Persian Gulf",
        description="Seizure of tankers and escalating naval confrontation",
        phases=[
            StatePhase("2019-05-01", "2019-05-11", "PEACE"),
            # May 12: Four tankers sabotaged
            StatePhase("2019-05-12", "2019-06-12", "CRISIS"),
            # Jun 13: Tankers attacked in Gulf of Oman
            StatePhase("2019-06-13", "2019-06-19", "LIMITED_STRIKES"),
            # Jun 20: US drone shot down — near-escalation
            StatePhase("2019-06-20", "2019-07-19", "CRISIS"),
            # Jul 19: Iran seizes Stena Impero
            StatePhase("2019-07-20", "2019-08-15", "CRISIS"),
        ],
    ),
    # ── 7. Nagorno-Karabakh 2020 ──────────────────────────────────
    BacktestScenario(
        name="Nagorno-Karabakh 2020",
        actors=["AZE", "ARM"],
        region="Caucasus",
        description="44-day war between Azerbaijan and Armenia",
        phases=[
            StatePhase("2020-09-01", "2020-09-26", "CRISIS"),
            # Sep 27: Full-scale Azerbaijani offensive — 44-day war begins
            StatePhase("2020-09-27", "2020-11-09", "ACTIVE_CONFLICT"),
            # Nov 10: Ceasefire agreement
            StatePhase("2020-11-10", "2020-11-15", "CRISIS"),
        ],
    ),
    # ── 8. Taiwan Strait Crisis 2022 ──────────────────────────────
    BacktestScenario(
        name="Taiwan Strait Crisis 2022",
        actors=["CHN", "TWN", "USA"],
        region="East Asia",
        description="Chinese military exercises around Taiwan after Pelosi visit",
        phases=[
            StatePhase("2022-07-15", "2022-08-01", "PEACE"),
            # Aug 2: Pelosi visits Taiwan
            StatePhase("2022-08-02", "2022-08-03", "CRISIS"),
            # Aug 4-7: PLA live-fire exercises, missile overflights
            StatePhase("2022-08-04", "2022-08-07", "LIMITED_STRIKES"),
            # Aug 8+: Exercises wind down, sustained posturing
            StatePhase("2022-08-08", "2022-08-20", "CRISIS"),
        ],
    ),
]

# ── Quick-access index ─────────────────────────────────────────────

_SCENARIO_MAP = {s.name: s for s in SCENARIOS}


def get_scenario(name: str) -> BacktestScenario:
    """Look up scenario by exact name.  Raises KeyError if not found."""
    if name in _SCENARIO_MAP:
        return _SCENARIO_MAP[name]
    # Fuzzy fallback
    name_lower = name.lower()
    for key, scenario in _SCENARIO_MAP.items():
        if name_lower in key.lower():
            return scenario
    raise KeyError(f"Scenario not found: {name}")


def get_scenarios_by_region(region: str) -> List[BacktestScenario]:
    """Filter scenarios by region (case-insensitive partial match)."""
    region_lower = region.lower()
    return [s for s in SCENARIOS if region_lower in s.region.lower()]


def get_scenarios_by_actor(actor: str) -> List[BacktestScenario]:
    """Filter scenarios involving a specific actor code."""
    actor_upper = actor.upper()
    return [s for s in SCENARIOS if actor_upper in s.actors]


__all__ = [
    "StatePhase",
    "BacktestScenario",
    "SCENARIOS",
    "get_scenario",
    "get_scenarios_by_region",
    "get_scenarios_by_actor",
    "get_ground_truth",
    "get_one_hot",
    "date_range",
    "generate_synthetic_signals",
    "build_mock_signals",
]
