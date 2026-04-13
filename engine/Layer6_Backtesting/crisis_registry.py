"""
Layer6_Backtesting — Crisis Registry
======================================

Defines historical crisis windows for backtesting the escalation
model.  Each crisis specifies:

    - Start date (when tension buildup began)
    - Escalation peak (when kinetic action / major event occurred)
    - Actors involved (FIPS codes)
    - Outcome type (conflict / standoff / de-escalation)

These windows are used by the replay engine to pull GDELT data
and simulate Phase 4 + Phase 5 outputs day-by-day.

Phase 6 ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class CrisisWindow:
    """A historical crisis for backtesting."""
    name: str
    start: str                          # ISO date: YYYY-MM-DD
    escalation_peak: str                # ISO date of kinetic onset or peak
    actors: List[str] = field(default_factory=list)
    outcome: str = "conflict"           # conflict / standoff / de-escalation
    region: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "start": self.start,
            "escalation_peak": self.escalation_peak,
            "actors": self.actors,
            "outcome": self.outcome,
            "region": self.region,
            "description": self.description,
        }


# ── Crisis Registry ──────────────────────────────────────────────────

CRISES: List[CrisisWindow] = [
    CrisisWindow(
        name="Crimea Annexation",
        start="2014-01-01",
        escalation_peak="2014-02-27",
        actors=["RUS", "UKR"],
        outcome="conflict",
        region="Eastern Europe",
        description="Russian annexation of Crimea following Euromaidan revolution",
    ),
    CrisisWindow(
        name="Ukraine Invasion",
        start="2021-10-01",
        escalation_peak="2022-02-24",
        actors=["RUS", "UKR"],
        outcome="conflict",
        region="Eastern Europe",
        description="Full-scale Russian invasion of Ukraine after months of buildup",
    ),
    CrisisWindow(
        name="Israel-Hamas War",
        start="2023-09-01",
        escalation_peak="2023-10-07",
        actors=["ISR", "PSE"],
        outcome="conflict",
        region="Middle East",
        description="Hamas attack on Israel triggering major conflict in Gaza",
    ),
    CrisisWindow(
        name="Iran-Saudi Tensions 2019",
        start="2019-08-01",
        escalation_peak="2019-09-14",
        actors=["IRN", "SAU"],
        outcome="standoff",
        region="Persian Gulf",
        description="Abqaiq-Khurais drone attacks on Saudi oil facilities",
    ),
    CrisisWindow(
        name="Soleimani Assassination",
        start="2019-12-01",
        escalation_peak="2020-01-03",
        actors=["IRN", "USA"],
        outcome="standoff",
        region="Persian Gulf",
        description="US assassination of Qasem Soleimani and subsequent escalation",
    ),
    CrisisWindow(
        name="Strait of Hormuz Tanker Crisis",
        start="2019-05-01",
        escalation_peak="2019-07-19",
        actors=["IRN", "GBR", "USA"],
        outcome="standoff",
        region="Persian Gulf",
        description="Seizure of tankers and escalating naval confrontation",
    ),
    CrisisWindow(
        name="Nagorno-Karabakh 2020",
        start="2020-09-01",
        escalation_peak="2020-09-27",
        actors=["AZE", "ARM"],
        outcome="conflict",
        region="Caucasus",
        description="44-day war between Azerbaijan and Armenia",
    ),
    CrisisWindow(
        name="Taiwan Strait Crisis 2022",
        start="2022-07-15",
        escalation_peak="2022-08-02",
        actors=["CHN", "TWN", "USA"],
        outcome="standoff",
        region="East Asia",
        description="Chinese military exercises around Taiwan after Pelosi visit",
    ),
]


def get_crisis_by_name(name: str) -> CrisisWindow:
    """Look up a crisis by name (case-insensitive partial match)."""
    name_lower = name.lower()
    for c in CRISES:
        if name_lower in c.name.lower():
            return c
    raise KeyError(f"Crisis not found: {name}")


def get_crises_by_region(region: str) -> List[CrisisWindow]:
    """Filter crises by region."""
    region_lower = region.lower()
    return [c for c in CRISES if region_lower in c.region.lower()]


def get_crises_by_actor(actor: str) -> List[CrisisWindow]:
    """Filter crises involving a specific actor."""
    actor_upper = actor.upper()
    return [c for c in CRISES if actor_upper in c.actors]
