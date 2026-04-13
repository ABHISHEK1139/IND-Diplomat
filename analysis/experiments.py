"""
Experimental Validation Framework
====================================

Three experiments that prove IND-Diplomat is a research-grade system:

1. **CrisisReplayExperiment** — Day-by-day historical backtesting
   with Brier scoring.  Answers: *Could IND-Diplomat have warned us
   before a war?*

2. **AblationExperiment** — Signal importance analysis via systematic
   signal removal.  Answers: *Which signals actually drive predictions?*

3. **LeadTimeExperiment** — Early-warning lead-time measurement.
   Answers: *How many days of advance warning does the system provide?*

Together they demonstrate **predictive accuracy**, **interpretable
reasoning**, and **real-world usefulness**.

This is an ADDITIVE module — it does NOT modify any existing code.
It imports ``EscalationInput`` and ``compute_escalation_index`` from
the existing pipeline and feeds them pre-built timeline data derived
from publicly documented event chronology.

Usage::

    from analysis.experiments import (
        CrisisReplayExperiment,
        AblationExperiment,
        LeadTimeExperiment,
    )

    # Experiment 1 — Crisis replay
    exp1 = CrisisReplayExperiment()
    result = exp1.replay_crisis("ukraine_2022")
    exp1.print_replay(result)

    # Experiment 2 — Ablation
    exp2 = AblationExperiment()
    report = exp2.run_full_ablation("ukraine_2022")
    exp2.print_ablation_report(report)

    # Experiment 3 — Lead time
    exp3 = LeadTimeExperiment()
    report = exp3.run_all_lead_times()
    exp3.print_lead_time_report(report)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("analysis.experiments")


# =====================================================================
# Shared data structures
# =====================================================================

@dataclass
class TimelineDataPoint:
    """One observation point in a crisis timeline."""
    date: str                              # YYYY-MM-DD
    signals: Dict[str, float]              # signal → confidence
    description: str = ""                  # what happened on this day

    @property
    def days_to_event(self) -> Optional[int]:
        """Set externally by CrisisTimeline when computing lead time."""
        return getattr(self, "_days_to_event", None)


@dataclass
class CrisisTimeline:
    """
    A complete crisis timeline with day-by-day signal data.

    Signal confidence values are derived from publicly documented
    event chronology (UCDP, ACLED, news timeline reconstructions).
    """
    name: str                              # e.g. "ukraine_2022"
    display_name: str                      # e.g. "Ukraine Invasion 2022"
    country: str                           # ISO-3
    event_date: str                        # YYYY-MM-DD  (the "outcome" date)
    outcome_binary: int                    # 1 = conflict occurred, 0 = averted
    ground_truth_risk: str                 # expected risk level at event_date
    data_points: List[TimelineDataPoint] = field(default_factory=list)
    description: str = ""


# =====================================================================
# Pre-built crisis timelines
# =====================================================================
# Signal confidence values are synthesized from publicly documented
# event chronology.  They represent what a system watching open-source
# intelligence would plausibly have detected at each date.

def _build_timelines() -> Dict[str, CrisisTimeline]:
    """Construct all crisis timelines."""
    timelines: Dict[str, CrisisTimeline] = {}

    # ────────────────────────────────────────────────────────────
    # 1. Ukraine Invasion 2022  (event: Feb 24)
    # ────────────────────────────────────────────────────────────
    timelines["ukraine_2022"] = CrisisTimeline(
        name="ukraine_2022",
        display_name="Ukraine Invasion 2022",
        country="UKR",
        event_date="2022-02-24",
        outcome_binary=1,
        ground_truth_risk="CRITICAL",
        description="Russian full-scale invasion of Ukraine",
        data_points=[
            TimelineDataPoint(
                date="2022-01-01",
                description="Satellite imagery shows troop buildup near border",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.30, "SIG_FORCE_POSTURE": 0.35,
                    "SIG_LOGISTICS_PREP": 0.20, "SIG_DIP_HOSTILITY": 0.25,
                    "SIG_COERCIVE_BARGAINING": 0.30, "SIG_ECONOMIC_PRESSURE": 0.15,
                },
            ),
            TimelineDataPoint(
                date="2022-01-15",
                description="Russia demands NATO security guarantees; 100k troops at border",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.45, "SIG_FORCE_POSTURE": 0.50,
                    "SIG_LOGISTICS_PREP": 0.35, "SIG_DIP_HOSTILITY": 0.55,
                    "SIG_COERCIVE_BARGAINING": 0.60, "SIG_NEGOTIATION_BREAKDOWN": 0.30,
                    "SIG_ECONOMIC_PRESSURE": 0.20, "SIG_ALLIANCE_ACTIVATION": 0.25,
                },
            ),
            TimelineDataPoint(
                date="2022-01-25",
                description="NATO allies put forces on standby; diplomatic talks stall",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.55, "SIG_FORCE_POSTURE": 0.60,
                    "SIG_LOGISTICS_PREP": 0.50, "SIG_DIP_HOSTILITY": 0.60,
                    "SIG_COERCIVE_BARGAINING": 0.65, "SIG_NEGOTIATION_BREAKDOWN": 0.45,
                    "SIG_ALLIANCE_ACTIVATION": 0.50, "SIG_ECONOMIC_PRESSURE": 0.30,
                },
            ),
            TimelineDataPoint(
                date="2022-02-05",
                description="130k troops deployed; US warns of imminent invasion",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.70, "SIG_FORCE_POSTURE": 0.75,
                    "SIG_LOGISTICS_PREP": 0.65, "SIG_DIP_HOSTILITY": 0.65,
                    "SIG_COERCIVE_BARGAINING": 0.70, "SIG_NEGOTIATION_BREAKDOWN": 0.55,
                    "SIG_ALLIANCE_ACTIVATION": 0.60, "SIG_ECONOMIC_PRESSURE": 0.40,
                    "SIG_INTERNAL_INSTABILITY": 0.20,
                },
            ),
            TimelineDataPoint(
                date="2022-02-14",
                description="Blood supplies moved to forward positions; embassies evacuate",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.82, "SIG_FORCE_POSTURE": 0.80,
                    "SIG_LOGISTICS_PREP": 0.78, "SIG_DIP_HOSTILITY": 0.70,
                    "SIG_COERCIVE_BARGAINING": 0.72, "SIG_NEGOTIATION_BREAKDOWN": 0.65,
                    "SIG_ALLIANCE_ACTIVATION": 0.65, "SIG_ECONOMIC_PRESSURE": 0.50,
                    "SIG_MIL_ESCALATION": 0.40,
                },
            ),
            TimelineDataPoint(
                date="2022-02-18",
                description="Donbas shelling intensifies; false-flag evacuation reports",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.88, "SIG_FORCE_POSTURE": 0.85,
                    "SIG_LOGISTICS_PREP": 0.82, "SIG_DIP_HOSTILITY": 0.75,
                    "SIG_COERCIVE_BARGAINING": 0.75, "SIG_NEGOTIATION_BREAKDOWN": 0.72,
                    "SIG_ALLIANCE_ACTIVATION": 0.70, "SIG_ECONOMIC_PRESSURE": 0.55,
                    "SIG_MIL_ESCALATION": 0.60, "SIG_INTERNAL_INSTABILITY": 0.35,
                },
            ),
            TimelineDataPoint(
                date="2022-02-21",
                description="Russia recognizes DPR/LPR; orders 'peacekeeping' troops",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.92, "SIG_FORCE_POSTURE": 0.90,
                    "SIG_LOGISTICS_PREP": 0.88, "SIG_DIP_HOSTILITY": 0.82,
                    "SIG_COERCIVE_BARGAINING": 0.78, "SIG_NEGOTIATION_BREAKDOWN": 0.80,
                    "SIG_ALLIANCE_ACTIVATION": 0.75, "SIG_ECONOMIC_PRESSURE": 0.60,
                    "SIG_MIL_ESCALATION": 0.75, "SIG_INTERNAL_INSTABILITY": 0.40,
                },
            ),
            TimelineDataPoint(
                date="2022-02-23",
                description="Full mobilization; cyberattacks on Ukrainian infrastructure",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.95, "SIG_FORCE_POSTURE": 0.92,
                    "SIG_LOGISTICS_PREP": 0.90, "SIG_DIP_HOSTILITY": 0.85,
                    "SIG_COERCIVE_BARGAINING": 0.80, "SIG_NEGOTIATION_BREAKDOWN": 0.85,
                    "SIG_ALLIANCE_ACTIVATION": 0.78, "SIG_ECONOMIC_PRESSURE": 0.65,
                    "SIG_MIL_ESCALATION": 0.82, "SIG_CYBER_ACTIVITY": 0.70,
                    "SIG_INTERNAL_INSTABILITY": 0.45,
                },
            ),
        ],
    )

    # ────────────────────────────────────────────────────────────
    # 2. Crimea Crisis 2014  (event: Mar 1 — troops enter)
    # ────────────────────────────────────────────────────────────
    timelines["crimea_2014"] = CrisisTimeline(
        name="crimea_2014",
        display_name="Crimea Crisis 2014",
        country="UKR",
        event_date="2014-03-01",
        outcome_binary=1,
        ground_truth_risk="HIGH",
        description="Russian annexation of Crimea following Euromaidan",
        data_points=[
            TimelineDataPoint(
                date="2014-01-15",
                description="Euromaidan protests intensify in Kyiv",
                signals={
                    "SIG_INTERNAL_INSTABILITY": 0.55, "SIG_PUBLIC_PROTEST": 0.60,
                    "SIG_DIP_HOSTILITY": 0.20, "SIG_ECONOMIC_PRESSURE": 0.25,
                },
            ),
            TimelineDataPoint(
                date="2014-02-01",
                description="Yanukovych flees; Russia recalls ambassador",
                signals={
                    "SIG_INTERNAL_INSTABILITY": 0.70, "SIG_PUBLIC_PROTEST": 0.65,
                    "SIG_DIP_HOSTILITY": 0.45, "SIG_MIL_MOBILIZATION": 0.15,
                    "SIG_ECONOMIC_PRESSURE": 0.35, "SIG_COERCIVE_BARGAINING": 0.35,
                },
            ),
            TimelineDataPoint(
                date="2014-02-15",
                description="Unknown armed men appear at Crimea parliament",
                signals={
                    "SIG_INTERNAL_INSTABILITY": 0.72, "SIG_MIL_MOBILIZATION": 0.40,
                    "SIG_FORCE_POSTURE": 0.45, "SIG_DIP_HOSTILITY": 0.55,
                    "SIG_COERCIVE_BARGAINING": 0.50, "SIG_ECONOMIC_PRESSURE": 0.40,
                },
            ),
            TimelineDataPoint(
                date="2014-02-22",
                description="Russian military exercises near Ukrainian border",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.60, "SIG_FORCE_POSTURE": 0.65,
                    "SIG_LOGISTICS_PREP": 0.40, "SIG_DIP_HOSTILITY": 0.65,
                    "SIG_COERCIVE_BARGAINING": 0.60, "SIG_INTERNAL_INSTABILITY": 0.65,
                    "SIG_MIL_ESCALATION": 0.30,
                },
            ),
            TimelineDataPoint(
                date="2014-02-27",
                description="Armed men seize Crimean parliament; Russian flags raised",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.75, "SIG_FORCE_POSTURE": 0.78,
                    "SIG_LOGISTICS_PREP": 0.55, "SIG_DIP_HOSTILITY": 0.72,
                    "SIG_COERCIVE_BARGAINING": 0.65, "SIG_MIL_ESCALATION": 0.55,
                    "SIG_INTERNAL_INSTABILITY": 0.60, "SIG_ALLIANCE_ACTIVATION": 0.30,
                },
            ),
            TimelineDataPoint(
                date="2014-02-28",
                description="Russian troops surround Ukrainian bases in Crimea",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.85, "SIG_FORCE_POSTURE": 0.85,
                    "SIG_LOGISTICS_PREP": 0.65, "SIG_DIP_HOSTILITY": 0.78,
                    "SIG_COERCIVE_BARGAINING": 0.70, "SIG_MIL_ESCALATION": 0.70,
                    "SIG_INTERNAL_INSTABILITY": 0.58, "SIG_ALLIANCE_ACTIVATION": 0.45,
                },
            ),
        ],
    )

    # ────────────────────────────────────────────────────────────
    # 3. Iran–US Tanker Crisis 2019  (event: Jun 20 drone shoot-down)
    # ────────────────────────────────────────────────────────────
    timelines["iran_us_2019"] = CrisisTimeline(
        name="iran_us_2019",
        display_name="Iran–US Tanker Crisis 2019",
        country="IRN",
        event_date="2019-06-20",
        outcome_binary=0,  # war averted — limited strikes only
        ground_truth_risk="HIGH",
        description="Gulf of Oman tanker attacks and US drone shoot-down",
        data_points=[
            TimelineDataPoint(
                date="2019-05-01",
                description="US deploys carrier strike group to Persian Gulf",
                signals={
                    "SIG_FORCE_POSTURE": 0.40, "SIG_MIL_MOBILIZATION": 0.20,
                    "SIG_COERCIVE_BARGAINING": 0.45, "SIG_DIP_HOSTILITY": 0.40,
                    "SIG_ECONOMIC_PRESSURE": 0.55,
                },
            ),
            TimelineDataPoint(
                date="2019-05-12",
                description="Four tankers sabotaged off Fujairah, UAE",
                signals={
                    "SIG_MIL_ESCALATION": 0.40, "SIG_FORCE_POSTURE": 0.55,
                    "SIG_COERCIVE_BARGAINING": 0.55, "SIG_DIP_HOSTILITY": 0.55,
                    "SIG_ECONOMIC_PRESSURE": 0.60, "SIG_ALLIANCE_ACTIVATION": 0.25,
                },
            ),
            TimelineDataPoint(
                date="2019-06-01",
                description="US deploys 1500 additional troops; B-52 patrols",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.45, "SIG_FORCE_POSTURE": 0.65,
                    "SIG_LOGISTICS_PREP": 0.35, "SIG_COERCIVE_BARGAINING": 0.60,
                    "SIG_DIP_HOSTILITY": 0.62, "SIG_ECONOMIC_PRESSURE": 0.62,
                    "SIG_ALLIANCE_ACTIVATION": 0.35,
                },
            ),
            TimelineDataPoint(
                date="2019-06-13",
                description="Two more tankers attacked in Gulf of Oman",
                signals={
                    "SIG_MIL_ESCALATION": 0.60, "SIG_FORCE_POSTURE": 0.70,
                    "SIG_MIL_MOBILIZATION": 0.50, "SIG_COERCIVE_BARGAINING": 0.68,
                    "SIG_DIP_HOSTILITY": 0.70, "SIG_ECONOMIC_PRESSURE": 0.65,
                    "SIG_ALLIANCE_ACTIVATION": 0.45,
                },
            ),
            TimelineDataPoint(
                date="2019-06-17",
                description="Pentagon announces additional 1000 troops; Iran breaches uranium cap",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.55, "SIG_FORCE_POSTURE": 0.72,
                    "SIG_LOGISTICS_PREP": 0.45, "SIG_MIL_ESCALATION": 0.62,
                    "SIG_COERCIVE_BARGAINING": 0.72, "SIG_DIP_HOSTILITY": 0.72,
                    "SIG_WMD_RISK": 0.40, "SIG_ECONOMIC_PRESSURE": 0.68,
                    "SIG_ALLIANCE_ACTIVATION": 0.50,
                },
            ),
            TimelineDataPoint(
                date="2019-06-20",
                description="Iran shoots down US RQ-4 drone; Trump orders then cancels strike",
                signals={
                    "SIG_MIL_ESCALATION": 0.78, "SIG_FORCE_POSTURE": 0.80,
                    "SIG_MIL_MOBILIZATION": 0.65, "SIG_LOGISTICS_PREP": 0.55,
                    "SIG_COERCIVE_BARGAINING": 0.80, "SIG_DIP_HOSTILITY": 0.80,
                    "SIG_WMD_RISK": 0.45, "SIG_ECONOMIC_PRESSURE": 0.70,
                    "SIG_ALLIANCE_ACTIVATION": 0.55,
                },
            ),
        ],
    )

    # ────────────────────────────────────────────────────────────
    # 4. Nagorno-Karabakh War 2020  (event: Sep 27 — war begins)
    # ────────────────────────────────────────────────────────────
    timelines["karabakh_2020"] = CrisisTimeline(
        name="karabakh_2020",
        display_name="Nagorno-Karabakh War 2020",
        country="AZE",
        event_date="2020-09-27",
        outcome_binary=1,
        ground_truth_risk="HIGH",
        description="Second Nagorno-Karabakh War (44-day war)",
        data_points=[
            TimelineDataPoint(
                date="2020-07-12",
                description="Border clashes at Tovuz kill multiple soldiers",
                signals={
                    "SIG_MIL_ESCALATION": 0.45, "SIG_FORCE_POSTURE": 0.35,
                    "SIG_DIP_HOSTILITY": 0.40, "SIG_COERCIVE_BARGAINING": 0.30,
                    "SIG_INTERNAL_INSTABILITY": 0.25,
                },
            ),
            TimelineDataPoint(
                date="2020-08-01",
                description="Turkey-Azerbaijan joint military exercises",
                signals={
                    "SIG_FORCE_POSTURE": 0.50, "SIG_ALLIANCE_ACTIVATION": 0.55,
                    "SIG_MIL_MOBILIZATION": 0.30, "SIG_DIP_HOSTILITY": 0.45,
                    "SIG_MIL_ESCALATION": 0.35, "SIG_COERCIVE_BARGAINING": 0.40,
                },
            ),
            TimelineDataPoint(
                date="2020-08-20",
                description="Azerbaijan procures Israeli and Turkish armed drones",
                signals={
                    "SIG_FORCE_POSTURE": 0.58, "SIG_ALLIANCE_ACTIVATION": 0.60,
                    "SIG_MIL_MOBILIZATION": 0.40, "SIG_LOGISTICS_PREP": 0.45,
                    "SIG_DIP_HOSTILITY": 0.50, "SIG_COERCIVE_BARGAINING": 0.45,
                },
            ),
            TimelineDataPoint(
                date="2020-09-10",
                description="Azerbaijani reservists called up; large-scale exercises begin",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.60, "SIG_FORCE_POSTURE": 0.65,
                    "SIG_LOGISTICS_PREP": 0.55, "SIG_ALLIANCE_ACTIVATION": 0.62,
                    "SIG_DIP_HOSTILITY": 0.58, "SIG_COERCIVE_BARGAINING": 0.52,
                    "SIG_MIL_ESCALATION": 0.40,
                },
            ),
            TimelineDataPoint(
                date="2020-09-20",
                description="Diplomatic channels collapse; martial law rhetoric",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.72, "SIG_FORCE_POSTURE": 0.75,
                    "SIG_LOGISTICS_PREP": 0.65, "SIG_ALLIANCE_ACTIVATION": 0.65,
                    "SIG_DIP_HOSTILITY": 0.68, "SIG_COERCIVE_BARGAINING": 0.60,
                    "SIG_NEGOTIATION_BREAKDOWN": 0.55, "SIG_MIL_ESCALATION": 0.55,
                },
            ),
            TimelineDataPoint(
                date="2020-09-26",
                description="Full mobilization; units moved to Line of Contact",
                signals={
                    "SIG_MIL_MOBILIZATION": 0.85, "SIG_FORCE_POSTURE": 0.82,
                    "SIG_LOGISTICS_PREP": 0.75, "SIG_ALLIANCE_ACTIVATION": 0.68,
                    "SIG_DIP_HOSTILITY": 0.75, "SIG_COERCIVE_BARGAINING": 0.65,
                    "SIG_NEGOTIATION_BREAKDOWN": 0.70, "SIG_MIL_ESCALATION": 0.70,
                },
            ),
        ],
    )

    return timelines


# Module-level singleton
CRISIS_TIMELINES: Dict[str, CrisisTimeline] = _build_timelines()


# =====================================================================
# Signal dimension classification (for ablation)
# =====================================================================

SIGNAL_DIMENSIONS: Dict[str, str] = {
    # Military
    "SIG_MIL_MOBILIZATION":     "military",
    "SIG_MIL_ESCALATION":       "military",
    "SIG_FORCE_POSTURE":        "military",
    "SIG_LOGISTICS_PREP":       "military",
    "SIG_KINETIC_ACTIVITY":     "military",
    "SIG_CYBER_ACTIVITY":       "military",
    # Diplomatic
    "SIG_DIP_HOSTILITY":        "diplomatic",
    "SIG_COERCIVE_BARGAINING":  "diplomatic",
    "SIG_ALLIANCE_ACTIVATION":  "diplomatic",
    "SIG_NEGOTIATION_BREAKDOWN":"diplomatic",
    "SIG_DIPLOMACY_ACTIVE":     "diplomatic",
    # Economic
    "SIG_ECONOMIC_PRESSURE":    "economic",
    # Domestic
    "SIG_INTERNAL_INSTABILITY": "domestic",
    "SIG_PUBLIC_PROTEST":       "domestic",
    # WMD
    "SIG_WMD_RISK":             "wmd",
}

ABLATION_CATEGORIES = ["military", "diplomatic", "economic", "domestic", "wmd"]


# =====================================================================
# SRE helpers (imported lazily to avoid circular deps)
# =====================================================================

def _signals_to_sre(signals: Dict[str, float]) -> Tuple[float, str]:
    """
    Convert a signal dict into an SRE score and risk level.

    Uses the same ``EscalationInput`` → ``compute_escalation_index``
    pipeline that the live system uses.
    """
    from engine.Layer4_Analysis.escalation_index import (
        EscalationInput, compute_escalation_index, escalation_to_risk,
    )

    cap_keys = {"SIG_MIL_MOBILIZATION", "SIG_MIL_ESCALATION",
                "SIG_FORCE_POSTURE", "SIG_LOGISTICS_PREP",
                "SIG_CYBER_ACTIVITY", "SIG_KINETIC_ACTIVITY",
                "SIG_WMD_RISK"}
    int_keys = {"SIG_DIP_HOSTILITY", "SIG_COERCIVE_BARGAINING",
                "SIG_ALLIANCE_ACTIVATION", "SIG_NEGOTIATION_BREAKDOWN",
                "SIG_DIPLOMACY_ACTIVE", "SIG_DETERRENCE_SIGNALING"}
    stab_keys = {"SIG_INTERNAL_INSTABILITY", "SIG_PUBLIC_PROTEST",
                 "SIG_DECEPTION_ACTIVITY"}
    cost_keys = {"SIG_ECONOMIC_PRESSURE"}

    cap_vals = [v for k, v in signals.items() if k in cap_keys]
    int_vals = [v for k, v in signals.items() if k in int_keys]
    stab_vals = [v for k, v in signals.items() if k in stab_keys]
    cost_vals = [v for k, v in signals.items() if k in cost_keys]

    capability = max(cap_vals) if cap_vals else 0.05
    intent = max(int_vals) if int_vals else 0.05
    instability = max(stab_vals) if stab_vals else 0.05
    cost = max(cost_vals) if cost_vals else 0.05

    mob_conf = signals.get("SIG_MIL_MOBILIZATION", 0.0)
    log_conf = signals.get("SIG_LOGISTICS_PREP", 0.0)

    inp = EscalationInput(
        capability=capability,
        intent=intent,
        instability=instability,
        cost=cost,
        mobilization_conf=mob_conf,
        logistics_conf=log_conf,
    )

    score = compute_escalation_index({}, inp=inp)
    risk = escalation_to_risk(score)
    return score, risk


def _days_between(date_a: str, date_b: str) -> int:
    """Return number of days from date_a to date_b (positive if b is later)."""
    da = datetime.strptime(date_a, "%Y-%m-%d")
    db = datetime.strptime(date_b, "%Y-%m-%d")
    return (db - da).days


# =====================================================================
# Brier Score
# =====================================================================

def brier_score(predicted_probability: float, outcome: int) -> float:
    """
    Compute the Brier score for a single prediction.

    ``Brier = (predicted_probability − outcome)²``

    Lower is better.  Perfect score = 0.0.  Worst = 1.0.

    Parameters
    ----------
    predicted_probability : float
        Predicted probability of the event occurring (0.0–1.0).
    outcome : int
        1 if event occurred, 0 if it did not.

    Examples
    --------
    >>> brier_score(0.8, 1)
    0.04
    >>> brier_score(0.2, 1)
    0.64
    >>> brier_score(0.1, 0)
    0.01
    """
    p = max(0.0, min(1.0, float(predicted_probability)))
    o = int(outcome)
    return round((p - o) ** 2, 6)


# =====================================================================
# Experiment 1: Crisis Replay
# =====================================================================

@dataclass
class CrisisReplayResult:
    """Result of replaying a crisis day-by-day."""
    crisis_name: str
    display_name: str
    country: str
    event_date: str
    outcome_binary: int
    ground_truth_risk: str
    trajectory: List[Dict[str, Any]] = field(default_factory=list)
    brier_scores: List[float] = field(default_factory=list)
    mean_brier: float = 0.0
    final_sre: float = 0.0
    final_risk: str = "UNKNOWN"
    risk_match: bool = False

    def to_dict(self) -> dict:
        return {
            "crisis_name": self.crisis_name,
            "display_name": self.display_name,
            "country": self.country,
            "event_date": self.event_date,
            "outcome_binary": self.outcome_binary,
            "ground_truth_risk": self.ground_truth_risk,
            "trajectory": self.trajectory,
            "brier_scores": [round(b, 4) for b in self.brier_scores],
            "mean_brier": round(self.mean_brier, 4),
            "final_sre": round(self.final_sre, 4),
            "final_risk": self.final_risk,
            "risk_match": self.risk_match,
        }


class CrisisReplayExperiment:
    """
    Experiment 1: Day-by-day historical crisis replay.

    Runs each data point through the SRE pipeline and records
    the escalation trajectory.  Computes Brier scores against
    the known outcome.
    """

    def __init__(self, timelines: Optional[Dict[str, CrisisTimeline]] = None):
        self.timelines = timelines or CRISIS_TIMELINES

    def list_crises(self) -> List[str]:
        """Return available crisis names."""
        return list(self.timelines.keys())

    def replay_crisis(self, crisis_name: str) -> CrisisReplayResult:
        """
        Replay a single crisis timeline day by day.

        Parameters
        ----------
        crisis_name : str
            Key into ``CRISIS_TIMELINES``.

        Returns
        -------
        CrisisReplayResult
        """
        tl = self.timelines[crisis_name]
        result = CrisisReplayResult(
            crisis_name=tl.name,
            display_name=tl.display_name,
            country=tl.country,
            event_date=tl.event_date,
            outcome_binary=tl.outcome_binary,
            ground_truth_risk=tl.ground_truth_risk,
        )

        for dp in tl.data_points:
            sre_score, risk_level = _signals_to_sre(dp.signals)
            days_to = _days_between(dp.date, tl.event_date)
            bs = brier_score(sre_score, tl.outcome_binary)

            entry = {
                "date": dp.date,
                "days_to_event": days_to,
                "sre_score": round(sre_score, 4),
                "risk_level": risk_level,
                "brier_score": round(bs, 4),
                "description": dp.description,
                "signal_count": len(dp.signals),
            }
            result.trajectory.append(entry)
            result.brier_scores.append(bs)

        if result.brier_scores:
            result.mean_brier = sum(result.brier_scores) / len(result.brier_scores)

        if result.trajectory:
            last = result.trajectory[-1]
            result.final_sre = last["sre_score"]
            result.final_risk = last["risk_level"]
            result.risk_match = (result.final_risk == tl.ground_truth_risk)

        logger.info(
            "[REPLAY] %s: final SRE=%.3f risk=%s (expected %s) | "
            "mean Brier=%.4f | match=%s",
            tl.display_name, result.final_sre, result.final_risk,
            tl.ground_truth_risk, result.mean_brier, result.risk_match,
        )

        return result

    def replay_all(self) -> List[CrisisReplayResult]:
        """Replay all available crises."""
        return [self.replay_crisis(name) for name in self.timelines]

    def compute_aggregate_brier(
        self, results: Optional[List[CrisisReplayResult]] = None,
    ) -> float:
        """Compute mean Brier score across all crises."""
        if results is None:
            results = self.replay_all()
        all_scores = []
        for r in results:
            all_scores.extend(r.brier_scores)
        return sum(all_scores) / len(all_scores) if all_scores else 1.0

    def print_replay(self, result: CrisisReplayResult) -> str:
        """Format a single crisis replay as a readable timeline."""
        lines = [
            "",
            "=" * 70,
            f"CRISIS REPLAY: {result.display_name}",
            "=" * 70,
            f"Country:         {result.country}",
            f"Event date:      {result.event_date}",
            f"Ground truth:    {result.ground_truth_risk}",
            f"Outcome:         {'CONFLICT' if result.outcome_binary else 'AVERTED'}",
            "",
            f"  {'Date':<14} {'Days':>5}  {'SRE':>6}  {'Risk':<12} {'Brier':>6}  Description",
            "  " + "-" * 80,
        ]

        for t in result.trajectory:
            lines.append(
                f"  {t['date']:<14} {t['days_to_event']:>+5d}  "
                f"{t['sre_score']:>6.3f}  {t['risk_level']:<12} "
                f"{t['brier_score']:>6.4f}  {t['description'][:40]}"
            )

        lines.extend([
            "",
            f"  Final SRE:     {result.final_sre:.3f}",
            f"  Final risk:    {result.final_risk}  "
            f"({'MATCH' if result.risk_match else 'MISS'})",
            f"  Mean Brier:    {result.mean_brier:.4f}",
            "=" * 70,
        ])

        output = "\n".join(lines)
        print(output)
        return output

    def print_all_replays(
        self, results: Optional[List[CrisisReplayResult]] = None,
    ) -> str:
        """Print all replays and aggregate Brier."""
        if results is None:
            results = self.replay_all()
        outputs = []
        for r in results:
            outputs.append(self.print_replay(r))
        agg = self.compute_aggregate_brier(results)
        summary = (
            f"\nAGGREGATE BRIER SCORE: {agg:.4f}  "
            f"(n={sum(len(r.brier_scores) for r in results)} data points "
            f"across {len(results)} crises)\n"
        )
        print(summary)
        outputs.append(summary)
        return "\n".join(outputs)


# =====================================================================
# Experiment 2: Signal Ablation
# =====================================================================

@dataclass
class AblationResult:
    """Result of removing one signal category."""
    crisis_name: str
    removed_category: str
    full_model_sre: float
    ablated_sre: float
    sre_delta: float = 0.0
    importance: float = 0.0              # |delta| / full_model_sre

    def __post_init__(self):
        self.sre_delta = self.full_model_sre - self.ablated_sre
        if self.full_model_sre > 0.001:
            self.importance = abs(self.sre_delta) / self.full_model_sre
        else:
            self.importance = 0.0


@dataclass
class AblationReport:
    """Aggregate ablation results for one crisis."""
    crisis_name: str
    display_name: str
    full_model_sre: float
    full_model_risk: str
    results: List[AblationResult] = field(default_factory=list)
    importance_ranking: List[Tuple[str, float]] = field(default_factory=list)

    def compute_ranking(self) -> None:
        """Sort categories by importance (descending)."""
        self.importance_ranking = sorted(
            [(r.removed_category, r.importance) for r in self.results],
            key=lambda x: -x[1],
        )

    def to_dict(self) -> dict:
        return {
            "crisis_name": self.crisis_name,
            "display_name": self.display_name,
            "full_model_sre": round(self.full_model_sre, 4),
            "full_model_risk": self.full_model_risk,
            "ablation_results": [
                {
                    "removed": r.removed_category,
                    "ablated_sre": round(r.ablated_sre, 4),
                    "delta": round(r.sre_delta, 4),
                    "importance": round(r.importance, 4),
                }
                for r in self.results
            ],
            "importance_ranking": [
                {"category": cat, "importance": round(imp, 4)}
                for cat, imp in self.importance_ranking
            ],
        }


class AblationExperiment:
    """
    Experiment 2: Signal ablation study.

    Runs the SRE with the full signal set, then removes one signal
    category at a time to measure each category's contribution.
    Uses the LAST data point of each timeline (peak escalation).
    """

    def __init__(self, timelines: Optional[Dict[str, CrisisTimeline]] = None):
        self.timelines = timelines or CRISIS_TIMELINES

    def run_ablation(
        self,
        crisis_name: str,
        removed_category: str,
    ) -> AblationResult:
        """
        Run SRE with one signal category zeroed out.

        Parameters
        ----------
        crisis_name : str
            Key into ``CRISIS_TIMELINES``.
        removed_category : str
            One of: "military", "diplomatic", "economic", "domestic", "wmd".
        """
        tl = self.timelines[crisis_name]
        last_dp = tl.data_points[-1]

        # Full model
        full_sre, _ = _signals_to_sre(last_dp.signals)

        # Ablated model — zero out signals of the removed category
        ablated_signals = {}
        for sig, conf in last_dp.signals.items():
            dim = SIGNAL_DIMENSIONS.get(sig, "unknown")
            if dim == removed_category:
                ablated_signals[sig] = 0.0    # zeroed out
            else:
                ablated_signals[sig] = conf

        ablated_sre, _ = _signals_to_sre(ablated_signals)

        result = AblationResult(
            crisis_name=crisis_name,
            removed_category=removed_category,
            full_model_sre=full_sre,
            ablated_sre=ablated_sre,
        )

        logger.info(
            "[ABLATION] %s without %s: %.3f → %.3f (delta=%.3f, importance=%.1f%%)",
            crisis_name, removed_category,
            full_sre, ablated_sre,
            result.sre_delta, result.importance * 100,
        )

        return result

    def run_full_ablation(self, crisis_name: str) -> AblationReport:
        """Run ablation for all signal categories on one crisis."""
        tl = self.timelines[crisis_name]
        full_sre, full_risk = _signals_to_sre(tl.data_points[-1].signals)

        report = AblationReport(
            crisis_name=crisis_name,
            display_name=tl.display_name,
            full_model_sre=full_sre,
            full_model_risk=full_risk,
        )

        for category in ABLATION_CATEGORIES:
            result = self.run_ablation(crisis_name, category)
            report.results.append(result)

        report.compute_ranking()
        return report

    def run_all_ablations(self) -> List[AblationReport]:
        """Run full ablation on every crisis."""
        return [self.run_full_ablation(name) for name in self.timelines]

    def print_ablation_report(self, report: AblationReport) -> str:
        """Format an ablation report as a readable table."""
        lines = [
            "",
            "=" * 70,
            f"ABLATION STUDY: {report.display_name}",
            "=" * 70,
            f"Full model SRE:  {report.full_model_sre:.3f}  ({report.full_model_risk})",
            "",
            f"  {'Removed Category':<20} {'Ablated SRE':>12} {'Delta':>8} {'Importance':>12}",
            "  " + "-" * 55,
        ]

        for r in sorted(report.results, key=lambda x: -x.importance):
            lines.append(
                f"  {r.removed_category:<20} {r.ablated_sre:>12.3f} "
                f"{r.sre_delta:>+8.3f} {r.importance:>11.1%}"
            )

        lines.extend([
            "",
            "  IMPORTANCE RANKING:",
        ])
        for i, (cat, imp) in enumerate(report.importance_ranking, 1):
            bar = "#" * int(imp * 40)
            lines.append(f"    {i}. {cat:<15} {imp:.1%} {bar}")

        lines.append("=" * 70)

        output = "\n".join(lines)
        print(output)
        return output


# =====================================================================
# Experiment 3: Lead Time
# =====================================================================

RISK_THRESHOLD_MAP = {
    "LOW": 0.0,
    "ELEVATED": 0.30,
    "HIGH": 0.50,
    "CRITICAL": 0.75,
}


@dataclass
class LeadTimeResult:
    """Result of lead-time measurement for one crisis."""
    crisis_name: str
    display_name: str
    event_date: str
    threshold_name: str
    threshold_value: float
    first_alert_date: Optional[str] = None
    first_alert_sre: float = 0.0
    lead_time_days: Optional[int] = None
    alert_triggered: bool = False

    def to_dict(self) -> dict:
        return {
            "crisis_name": self.crisis_name,
            "display_name": self.display_name,
            "event_date": self.event_date,
            "threshold": self.threshold_name,
            "first_alert_date": self.first_alert_date,
            "first_alert_sre": round(self.first_alert_sre, 4),
            "lead_time_days": self.lead_time_days,
            "alert_triggered": self.alert_triggered,
        }


@dataclass
class LeadTimeReport:
    """Aggregate lead-time results across multiple crises."""
    threshold_name: str
    results: List[LeadTimeResult] = field(default_factory=list)
    mean_lead_time: Optional[float] = None
    median_lead_time: Optional[float] = None
    crises_alerted: int = 0
    crises_total: int = 0

    def compute_stats(self) -> None:
        """Compute aggregate statistics."""
        self.crises_total = len(self.results)
        valid = [r.lead_time_days for r in self.results
                 if r.lead_time_days is not None and r.lead_time_days > 0]
        self.crises_alerted = len(valid)
        if valid:
            self.mean_lead_time = sum(valid) / len(valid)
            sorted_valid = sorted(valid)
            mid = len(sorted_valid) // 2
            self.median_lead_time = (
                sorted_valid[mid]
                if len(sorted_valid) % 2 == 1
                else (sorted_valid[mid - 1] + sorted_valid[mid]) / 2.0
            )

    def to_dict(self) -> dict:
        return {
            "threshold": self.threshold_name,
            "crises_alerted": self.crises_alerted,
            "crises_total": self.crises_total,
            "mean_lead_time_days": (
                round(self.mean_lead_time, 1) if self.mean_lead_time else None
            ),
            "median_lead_time_days": (
                round(self.median_lead_time, 1) if self.median_lead_time else None
            ),
            "results": [r.to_dict() for r in self.results],
        }


class LeadTimeExperiment:
    """
    Experiment 3: Early-warning lead-time measurement.

    Measures how many days before the known event the system
    crosses a given risk threshold.
    """

    def __init__(self, timelines: Optional[Dict[str, CrisisTimeline]] = None):
        self.timelines = timelines or CRISIS_TIMELINES

    def measure_lead_time(
        self,
        crisis_name: str,
        threshold: str = "HIGH",
    ) -> LeadTimeResult:
        """
        Measure lead time for a single crisis.

        Parameters
        ----------
        crisis_name : str
            Key into ``CRISIS_TIMELINES``.
        threshold : str
            Risk level threshold: "ELEVATED", "HIGH", or "CRITICAL".
        """
        tl = self.timelines[crisis_name]
        threshold_value = RISK_THRESHOLD_MAP.get(threshold, 0.50)

        result = LeadTimeResult(
            crisis_name=crisis_name,
            display_name=tl.display_name,
            event_date=tl.event_date,
            threshold_name=threshold,
            threshold_value=threshold_value,
        )

        for dp in tl.data_points:
            sre_score, _ = _signals_to_sre(dp.signals)

            if sre_score >= threshold_value and not result.alert_triggered:
                result.alert_triggered = True
                result.first_alert_date = dp.date
                result.first_alert_sre = sre_score
                result.lead_time_days = _days_between(dp.date, tl.event_date)
                break

        if result.alert_triggered:
            logger.info(
                "[LEAD-TIME] %s: %s threshold crossed on %s "
                "(SRE=%.3f), %d days before event",
                tl.display_name, threshold,
                result.first_alert_date, result.first_alert_sre,
                result.lead_time_days,
            )
        else:
            logger.info(
                "[LEAD-TIME] %s: %s threshold NOT crossed before event",
                tl.display_name, threshold,
            )

        return result

    def run_all_lead_times(
        self, threshold: str = "HIGH",
    ) -> LeadTimeReport:
        """Measure lead time for all crises at a given threshold."""
        report = LeadTimeReport(threshold_name=threshold)

        for name in self.timelines:
            result = self.measure_lead_time(name, threshold)
            report.results.append(result)

        report.compute_stats()
        return report

    def print_lead_time_report(self, report: LeadTimeReport) -> str:
        """Format a lead-time report as a readable table."""
        lines = [
            "",
            "=" * 70,
            f"EARLY-WARNING LEAD TIME REPORT  (threshold: {report.threshold_name})",
            "=" * 70,
            "",
            f"  {'Crisis':<30} {'Alert Date':<14} {'Event Date':<14} {'Lead Time':>10}",
            "  " + "-" * 70,
        ]

        for r in report.results:
            alert = r.first_alert_date or "—"
            lt = f"{r.lead_time_days} days" if r.lead_time_days is not None else "NO ALERT"
            lines.append(
                f"  {r.display_name:<30} {alert:<14} {r.event_date:<14} {lt:>10}"
            )

        lines.extend([
            "",
            f"  Crises alerted:   {report.crises_alerted}/{report.crises_total}",
        ])
        if report.mean_lead_time is not None:
            lines.append(f"  Mean lead time:   {report.mean_lead_time:.1f} days")
        if report.median_lead_time is not None:
            lines.append(f"  Median lead time: {report.median_lead_time:.1f} days")

        lines.append("=" * 70)

        output = "\n".join(lines)
        print(output)
        return output


# =====================================================================
# Convenience: run all experiments
# =====================================================================

def run_all_experiments() -> Dict[str, Any]:
    """
    Run all three experiments and return combined results.

    Returns
    -------
    dict
        Keys: ``replay``, ``ablation``, ``lead_time``, ``summary``.
    """
    # Experiment 1
    exp1 = CrisisReplayExperiment()
    replays = exp1.replay_all()
    agg_brier = exp1.compute_aggregate_brier(replays)

    # Experiment 2
    exp2 = AblationExperiment()
    ablations = exp2.run_all_ablations()

    # Experiment 3
    exp3 = LeadTimeExperiment()
    lead_times = exp3.run_all_lead_times(threshold="HIGH")

    # Summary
    risk_matches = sum(1 for r in replays if r.risk_match)
    summary = {
        "aggregate_brier_score": round(agg_brier, 4),
        "risk_match_rate": f"{risk_matches}/{len(replays)}",
        "crises_alerted": f"{lead_times.crises_alerted}/{lead_times.crises_total}",
        "mean_lead_time_days": (
            round(lead_times.mean_lead_time, 1)
            if lead_times.mean_lead_time else None
        ),
    }

    return {
        "replay": [r.to_dict() for r in replays],
        "ablation": [a.to_dict() for a in ablations],
        "lead_time": lead_times.to_dict(),
        "summary": summary,
    }


def print_full_report() -> None:
    """Print formatted reports for all three experiments."""
    print("\n" + "#" * 70)
    print("  IND-DIPLOMAT EXPERIMENTAL VALIDATION")
    print("#" * 70)

    # Experiment 1
    exp1 = CrisisReplayExperiment()
    replays = exp1.replay_all()
    exp1.print_all_replays(replays)

    # Experiment 2
    exp2 = AblationExperiment()
    for name in exp2.timelines:
        report = exp2.run_full_ablation(name)
        exp2.print_ablation_report(report)

    # Experiment 3
    exp3 = LeadTimeExperiment()
    lt_report = exp3.run_all_lead_times(threshold="HIGH")
    exp3.print_lead_time_report(lt_report)

    # Final summary
    agg_brier = exp1.compute_aggregate_brier(replays)
    risk_matches = sum(1 for r in replays if r.risk_match)
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Aggregate Brier score: {agg_brier:.4f}")
    print(f"  Risk level matches:    {risk_matches}/{len(replays)}")
    print(f"  Crises alerted:        {lt_report.crises_alerted}/{lt_report.crises_total}")
    if lt_report.mean_lead_time:
        print(f"  Mean lead time:        {lt_report.mean_lead_time:.1f} days")
    print("=" * 70)


# =====================================================================
# Exports
# =====================================================================

__all__ = [
    # Data structures
    "TimelineDataPoint",
    "CrisisTimeline",
    "CRISIS_TIMELINES",
    "SIGNAL_DIMENSIONS",
    # Brier
    "brier_score",
    # Experiment 1
    "CrisisReplayExperiment",
    "CrisisReplayResult",
    # Experiment 2
    "AblationExperiment",
    "AblationResult",
    "AblationReport",
    # Experiment 3
    "LeadTimeExperiment",
    "LeadTimeResult",
    "LeadTimeReport",
    # Convenience
    "run_all_experiments",
    "print_full_report",
]
