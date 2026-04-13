"""
Geopolitical Signal Definitions
===============================
Standardized data structures for interpreted intelligence signals.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

class SignalType(Enum):
    EVENT = "event"          # What happened (conflict, cooperation)
    ECONOMIC = "economic"    # Economic pressure (inflation, debt)
    MILITARY = "military"    # Hard power capability & posture
    LEGAL = "legal"          # Treaty obligations & rights
    LEADERSHIP = "leadership"# Decision maker profile
    DIPLOMACY = "diplomacy"  # Alliances & diplomatic status

@dataclass
class BaseSignal:
    source: str              # e.g., "GDELT", "WorldBank", "SIPRI"
    confidence: float        # 0.0 to 1.0 reliability score
    timestamp: str           # ISO format date of the signal

@dataclass
class EventSignal(BaseSignal):
    """
    Interpretation of real-world events (GDELT/News).
    """
    tension_score: float     # 0.0 (peace) to 1.0 (war)
    goldstein_score: float   # Weighted average (-10 to +10)
    conflict_events: int     # Count of hostile actions
    cooperation_events: int  # Count of cooperative actions
    major_actors: List[str] = field(default_factory=list)
    top_themes: List[str] = field(default_factory=list)

@dataclass
class EconomicSignal(BaseSignal):
    """
    Interpretation of economic health and pressure.
    """
    vulnerability_score: float # 0.0 (resilient) to 1.0 (crises prone)
    inflation_pressure: str    # "low", "moderate", "high", "hyper"
    debt_stress: str           # "sustainable", "watch", "crisis"
    trade_dependency: Dict[str, float] = field(default_factory=dict) # partner -> dependency %

@dataclass
class MilitarySignal(BaseSignal):
    """
    Interpretation of military posture.
    """
    readiness_score: float   # 0.0 to 1.0
    mobilization_level: str  # "peace", "exercising", "mobilized", "war"
    recent_procurement: List[str] = field(default_factory=list)

@dataclass
class LegalSignal(BaseSignal):
    """
    Interpretation of legal standing.
    """
    treaty_compliance: float # 0.0 to 1.0
    active_disputes: int
    relevant_treaties: List[str] = field(default_factory=list)

@dataclass
class LeadershipSignal(BaseSignal):
    """
    Interpretation of leadership stability.
    """
    approval_rating: Optional[float]
    time_in_office: int      # months
    stability_risk: str      # "low", "medium", "coup_risk"
