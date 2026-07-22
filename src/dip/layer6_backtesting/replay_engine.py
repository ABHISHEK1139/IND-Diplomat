"""
Replay Engine (Layer 6)
=======================
Replays historical crises through the state model to test if the system
would have predicted them.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from dip.layer6_backtesting.crisis_registry import CRISIS_DATABASE
from dip.core.schema import Signal
from dip.layer3_state.belief_accumulator import evaluate
from dip.layer3_state.temporal_memory import compute_trends
from dip.layer3_state.conflict_state_model import compute_domain_indices, compute_escalation
from dip.layer6_backtesting.scenario_registry import BacktestScenario

logger = logging.getLogger("Layer6.replay")

@dataclass
class DaySnapshot:
    date: str = ""
    conflict_posterior: float = 0.0
    ground_truth_state: str = "LOW"
    conflict_state: str = "LOW"
    sre: float = 0.0
    conflict_confidence: float = 0.0
    gap_count: int = 0
    observed_groups: List[str] = field(default_factory=list)
    transition_matrix_row: List[float] = field(default_factory=list)
    p_active_or_higher_14d: float = 0.0
    learning_delta: float = 0.0

@dataclass
class ReplayResult:
    scenario_name: str
    crisis_name: str = ""
    snapshots: List[DaySnapshot] = field(default_factory=list)
    detection_timeline: List[Dict[str, Any]] = field(default_factory=list)
    lead_time_days: int = 0
    accuracy: float = 0.0
    error: Optional[str] = None
    days_count: int = 0
    peak_p_active: float = 0.0
    ground_truth_phases: List[str] = field(default_factory=list)
    matrix_before: List[List[float]] = field(default_factory=list)
    matrix_after: List[List[float]] = field(default_factory=list)


def replay_scenario(scenario: BacktestScenario) -> ReplayResult:
    result = ReplayResult(scenario_name=scenario.name, crisis_name=scenario.name)
    
    # We simulate passing the timeline into the state model day by day
    detected_peak = False
    
    for day_data in scenario.timeline:
        day = day_data.get("day", 0)
        signals_list = day_data.get("signals", [])
        
        signals = [
            Signal(entity="TEST", action=s, intensity=0.8, confidence=0.8, source_ref="DATASET")
            for s in signals_list
        ]
        
        beliefs = evaluate(signals)
        indicators = []
        domains = compute_domain_indices(beliefs, signals)
        escalation = compute_escalation(domains, indicators, beliefs)
        
        snapshot = DaySnapshot(
            date=str(day),
            conflict_state=escalation.threat_level,
            sre=escalation.escalation_score
        )
        result.snapshots.append(snapshot)
        result.days_count += 1
            
    result.accuracy = 1.0 if detected_peak else 0.0
    return result

def replay_crisis(crisis_name: str) -> dict:
    if crisis_name not in CRISIS_DATABASE:
        raise ValueError(f"Crisis {crisis_name} not found in registry.")
    crisis = CRISIS_DATABASE[crisis_name]
    scenario = BacktestScenario(name=crisis_name, country="UNKNOWN", start_date="", end_date="", timeline=crisis["timeline"])
    res = replay_scenario(scenario)
    return {
        "crisis_name": res.crisis_name,
        "timeline": [{"day": s.date, "threat_level": s.conflict_state, "score": s.sre} for s in res.snapshots],
        "lead_time_days": res.lead_time_days,
        "accuracy": res.accuracy
    }
