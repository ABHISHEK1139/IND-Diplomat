"""
Layer 3: Belief Accumulator
===========================
Converts raw signals into corroborated beliefs using fuzzy accumulation.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime
import math
from dip.core.schema import Signal, Belief
from dip.core.fuzzy import _clamp

logger = logging.getLogger("Layer3.belief_accumulator")

SOURCE_RELIABILITY = {
    "SOCIAL": 0.30,
    "OSINT": 0.55,
    "MOLTBOT": 0.55,
    "NEWS": 0.55,
    "GOV": 0.75,
    "UN": 0.80,
    "SIPRI": 0.85,
    "SENSOR": 0.90,
    "ANALYST": 0.90,
    "DATASET": 0.90,
}

# Exponential decay (half-life in hours)
RECENCY_HALF_LIFE_HOURS = 72.0

SOURCE_DIVERSITY_BONUS = 0.10
SOURCE_DIVERSITY_CAP = 0.20


def evaluate(signals: List[Signal]) -> List[Belief]:
    """
    Converts signals into beliefs by aggregating them by action (signal_code).
    """
    signal_groups: Dict[str, List[Signal]] = {}
    for s in signals:
        if s.action not in signal_groups:
            signal_groups[s.action] = []
        signal_groups[s.action].append(s)

    beliefs = []

    for action, grouped_signals in signal_groups.items():
        # Source diversity
        source_types = set()
        for s in grouped_signals:
            ref = s.source_ref.split("_")[0] if "_" in s.source_ref else "OSINT"
            source_types.add(ref)

        # Base support score: max confidence among signals
        base_support = max(s.confidence for s in grouped_signals) if grouped_signals else 0.0
        
        # Add diversity bonus
        diversity_bonus = min(SOURCE_DIVERSITY_CAP, (len(source_types) - 1) * SOURCE_DIVERSITY_BONUS)
        support_score = _clamp(base_support + diversity_bonus)

        # Belief level classification
        if support_score < 0.35:
            continue # Ignore
        elif support_score < 0.55:
            belief_level = "weak"
        elif support_score < 0.75:
            belief_level = "moderate"
        else:
            belief_level = "strong"

        b = Belief(
            signal_code=action,
            support_score=support_score,
            belief_level=belief_level,
            source_count=len(grouped_signals),
            recency_weight=1.0, # Without historical timestamp, assume 1.0 for now
            source_types=list(source_types)
        )
        beliefs.append(b)

    return beliefs
