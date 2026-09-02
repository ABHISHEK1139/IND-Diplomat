"""
Phase 11: Historical Backtesting Framework.

Replays historical crises through the IND-Diplomat pipeline
and compares forecasts against actual outcomes.

Metrics:
  - Brier Score
  - Calibration
  - Precision / Recall
  - Lead time (how early did we detect?)
  - False alarm rate
"""

import logging
import math
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

logger = logging.getLogger("Layer7.Backtesting")


class HistoricalCase(BaseModel):
    """A historical crisis case for backtesting."""
    case_id: str
    name: str
    description: str
    date_range: str  # e.g. "2024-10-01 to 2024-10-31"
    actual_outcome: str  # One of CONFLICT_STATES
    actual_probability: float  # Ground truth probability (0-1)
    signals: List[str] = Field(default_factory=list)  # Raw signal descriptions


class ForecastResult(BaseModel):
    """A forecast produced by the system for a historical case."""
    case_id: str
    predicted_state: str
    predicted_probability: float
    lead_time_days: int = 0  # How many days before the event was it predicted?
    agent_beliefs: Dict[str, float] = Field(default_factory=dict)


class BacktestMetrics(BaseModel):
    """Aggregated metrics from backtesting."""
    total_cases: int
    brier_score: float
    calibration_error: float
    precision: float
    recall: float
    mean_lead_time: float
    false_alarm_rate: float


# ── Built-in historical cases ──────────────────────────────────────────
HISTORICAL_CASES: List[HistoricalCase] = [
    HistoricalCase(
        case_id="KARGIL_1999",
        name="Kargil War 1999",
        description="Pakistani forces infiltrated across the Line of Control in Kargil sector.",
        date_range="1999-05-03 to 1999-07-26",
        actual_outcome="ACTIVE_CONFLICT",
        actual_probability=0.85,
        signals=[
            "Pakistan Army infiltration detected in Kargil sector",
            "Indian Army Operation Vijay launched",
            "Artillery exchanges across LOC",
            "IAF strikes on Kargil peaks",
        ],
    ),
    HistoricalCase(
        case_id="GALWAN_2020",
        name="Galwan Valley Clash 2020",
        description="Deadly clash between Indian and Chinese troops in Galwan Valley, Ladakh.",
        date_range="2020-06-15 to 2020-06-20",
        actual_outcome="LIMITED_CONFLICT",
        actual_probability=0.60,
        signals=[
            "Chinese PLA road construction in Galwan area",
            "Indian patrol confrontation with PLA",
            "20 Indian soldiers killed in hand-to-hand combat",
            "Both sides reinforcing positions in eastern Ladakh",
        ],
    ),
    HistoricalCase(
        case_id="DOKLAM_2017",
        name="Doklam Standoff 2017",
        description="73-day military standoff between India and China at Doklam plateau.",
        date_range="2017-06-16 to 2017-08-28",
        actual_outcome="CRISIS",
        actual_probability=0.40,
        signals=[
            "Chinese road construction in disputed Doklam area",
            "Indian troops block Chinese construction crews",
            "73-day standoff at tri-junction",
            "Diplomatic resolution without conflict",
        ],
    ),
    HistoricalCase(
        case_id="BALAKOT_2019",
        name="Balakot Strikes 2019",
        description="Indian Air Force strikes in Balakot, Pakistan following Pulwama terror attack.",
        date_range="2019-02-14 to 2019-03-01",
        actual_outcome="LIMITED_CONFLICT",
        actual_probability=0.65,
        signals=[
            "Pulwama VBIED attack kills 40 CRPF personnel",
            "IAF Mirage-2000 strikes on Balakot JeM camp",
            "PAF F-16 engagement, Wing Commander Abhinandan captured",
            "Nuclear-armed neighbors exchange air strikes",
        ],
    ),
    HistoricalCase(
        case_id="TAIWAN_STRAIT_2022",
        name="Taiwan Strait Crisis 2022",
        description="Chinese military exercises around Taiwan following Pelosi visit.",
        date_range="2022-08-02 to 2022-08-10",
        actual_outcome="CRISIS",
        actual_probability=0.35,
        signals=[
            "Speaker Pelosi visits Taiwan",
            "PLA announces live-fire exercises in 6 zones around Taiwan",
            "Ballistic missiles fired over Taiwan",
            "Naval blockade simulation exercises",
        ],
    ),
    HistoricalCase(
        case_id="UKRAINE_2022",
        name="Ukraine Invasion 2022",
        description="Russian military buildup and invasion of Ukraine.",
        date_range="2021-11-01 to 2022-02-24",
        actual_outcome="FULL_WAR",
        actual_probability=0.95,
        signals=[
            "190,000 Russian troops massed on Ukrainian border",
            "Blood supplies and field hospitals deployed to front lines",
            "Russian President announces 'special military operation'",
        ],
    ),
    HistoricalCase(
        case_id="CUBAN_MISSILE_1962",
        name="Cuban Missile Crisis 1962",
        description="13-day confrontation between US and Soviet Union over Soviet missiles in Cuba.",
        date_range="1962-10-16 to 1962-10-28",
        actual_outcome="CRISIS",
        actual_probability=0.45,
        signals=[
            "U-2 spy plane photographs Soviet nuclear missiles in Cuba",
            "US implements naval quarantine of Cuba",
            "DEFCON 2 declared by US Strategic Air Command",
            "Soviet ships turn back at quarantine line",
        ],
    ),
    HistoricalCase(
        case_id="SIX_DAY_WAR_1967",
        name="Six-Day War 1967",
        description="Israel launches preemptive strikes against Egypt, Syria, and Jordan.",
        date_range="1967-05-15 to 1967-06-05",
        actual_outcome="FULL_WAR",
        actual_probability=0.85,
        signals=[
            "Egypt expels UNEF forces from Sinai",
            "Egypt closes Straits of Tiran to Israeli shipping",
            "Arab armies mobilize on Israeli borders",
            "Israel launches Operation Focus",
        ],
    ),
    HistoricalCase(
        case_id="DESERT_STORM_1991",
        name="Operation Desert Storm 1991",
        description="Coalition forces launch air and ground assault to expel Iraq from Kuwait.",
        date_range="1990-08-02 to 1991-01-17",
        actual_outcome="FULL_WAR",
        actual_probability=0.90,
        signals=[
            "Iraq invades and annexes Kuwait",
            "UN Security Council Resolution 678 sets Jan 15 deadline",
            "US leads 35-nation coalition buildup in Saudi Arabia",
            "Deadline passes with no Iraqi withdrawal",
        ],
    ),
    HistoricalCase(
        case_id="RUSSIA_GEORGIA_2008",
        name="Russo-Georgian War 2008",
        description="Russian invasion of Georgia over South Ossetia.",
        date_range="2008-08-01 to 2008-08-12",
        actual_outcome="LIMITED_CONFLICT",
        actual_probability=0.75,
        signals=[
            "Artillery exchanges between Georgian and Ossetian forces",
            "Russian troops enter South Ossetia",
            "Russian cyberattacks paralyze Georgian networks",
            "Russian bombing of Georgian targets outside conflict zone",
        ],
    ),
    HistoricalCase(
        case_id="IRAN_ISRAEL_2024",
        name="Iran-Israel Direct Strikes 2024",
        description="First direct military confrontation between Iran and Israel.",
        date_range="2024-04-01 to 2024-04-19",
        actual_outcome="LIMITED_CONFLICT",
        actual_probability=0.80,
        signals=[
            "Israeli airstrike destroys Iranian consulate in Damascus",
            "Iran launches 300+ drones and ballistic missiles at Israel",
            "US and regional allies intercept 99% of projectiles",
            "Israel conducts retaliatory strike on air defense radar in Isfahan",
        ],
    ),
]


class BacktestEngine:
    """
    Runs historical cases through the forecast pipeline
    and computes accuracy metrics.
    """

    def __init__(self):
        self.results: List[ForecastResult] = []

    def add_result(self, result: ForecastResult):
        self.results.append(result)

    def compute_brier_score(self, cases: List[HistoricalCase]) -> float:
        """
        Brier Score = (1/N) * Σ (predicted - actual)²
        Lower is better. 0.0 = perfect, 0.25 = baseline.
        """
        if not self.results or not cases:
            return 1.0

        case_map = {c.case_id: c for c in cases}
        total = 0.0
        n = 0
        for r in self.results:
            if r.case_id in case_map:
                actual = case_map[r.case_id].actual_probability
                total += (r.predicted_probability - actual) ** 2
                n += 1

        return total / max(n, 1)

    def compute_calibration_error(self, cases: List[HistoricalCase]) -> float:
        """
        Mean absolute error between predicted and actual probabilities.
        """
        case_map = {c.case_id: c for c in cases}
        errors = []
        for r in self.results:
            if r.case_id in case_map:
                actual = case_map[r.case_id].actual_probability
                errors.append(abs(r.predicted_probability - actual))

        return sum(errors) / max(len(errors), 1)

    def compute_precision_recall(self, cases: List[HistoricalCase], threshold: float = 0.50):
        """
        Precision and Recall for conflict detection.
        Positive = predicted probability >= threshold AND actual state is conflict-like.
        """
        case_map = {c.case_id: c for c in cases}
        conflict_states = {"LIMITED_CONFLICT", "ACTIVE_CONFLICT", "FULL_WAR"}

        tp = fp = fn = tn = 0
        for r in self.results:
            case = case_map.get(r.case_id)
            if not case:
                continue
            predicted_positive = r.predicted_probability >= threshold
            actual_positive = case.actual_outcome in conflict_states

            if predicted_positive and actual_positive:
                tp += 1
            elif predicted_positive and not actual_positive:
                fp += 1
            elif not predicted_positive and actual_positive:
                fn += 1
            else:
                tn += 1

        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        false_alarm = fp / max(fp + tn, 1)

        return precision, recall, false_alarm

    def compute_metrics(self, cases: Optional[List[HistoricalCase]] = None) -> BacktestMetrics:
        """Compute all backtesting metrics."""
        if cases is None:
            cases = HISTORICAL_CASES

        brier = self.compute_brier_score(cases)
        calibration = self.compute_calibration_error(cases)
        precision, recall, false_alarm = self.compute_precision_recall(cases)
        lead_times = [r.lead_time_days for r in self.results if r.lead_time_days > 0]
        mean_lead = sum(lead_times) / max(len(lead_times), 1)

        metrics = BacktestMetrics(
            total_cases=len(self.results),
            brier_score=round(brier, 4),
            calibration_error=round(calibration, 4),
            precision=round(precision, 4),
            recall=round(recall, 4),
            mean_lead_time=round(mean_lead, 2),
            false_alarm_rate=round(false_alarm, 4),
        )

        logger.info(f"[Backtesting] Brier={metrics.brier_score} Cal={metrics.calibration_error} "
                     f"Prec={metrics.precision} Rec={metrics.recall} FAR={metrics.false_alarm_rate}")
        return metrics
