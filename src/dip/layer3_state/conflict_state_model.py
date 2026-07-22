"""
Layer 3: Conflict State Model
=============================
Computes the escalation index and multidimensional state.
"""

from typing import List
from dip.core.schema import Belief, Signal, TemporalIndicator, DomainIndex, EscalationResult
from dip.core.fuzzy import rising, _clamp
from dip.layer3_state.adversary_intent_model import IntentAnalyzer

W_CAPABILITY = 0.35
W_INTENT = 0.30
W_INSTABILITY = 0.20
W_COST = 0.15

TREND_BONUS_CAP = 0.20
CAPABILITY_FLOOR = 0.30


def compute_domain_indices(beliefs: List[Belief], signals: List[Signal] = None) -> DomainIndex:
    # A mapping from signal substrings to domains could be more elaborate,
    # but for now we'll do a simple keyword match.
    domains = {"capability": [], "intent": [], "instability": [], "cost": [], "logistics": []}
    
    for b in beliefs:
        code = b.signal_code.lower()
        if "mil_" in code or "force" in code or "mobilization" in code:
            domains["capability"].append(b.support_score)
        if "escalation" in code or "hostil" in code or "pressure" in code or "threat" in code:
            domains["intent"].append(b.support_score)
        if "unrest" in code or "instab" in code or "protest" in code:
            domains["instability"].append(b.support_score)
        if "econ" in code or "sanction" in code or "breakdown" in code:
            domains["cost"].append(b.support_score)
        if "logistic" in code or "supply" in code:
            domains["logistics"].append(b.support_score)

    def fuzzy_agg(scores: List[float]) -> float:
        if not scores: return 0.0
        # Give more weight to higher scores (like fuzzy max)
        return min(1.0, max(scores) * 1.2)

    intent_profile = {}
    if signals:
        analyzer = IntentAnalyzer()
        intent_profile = analyzer.analyze(signals)

    return DomainIndex(
        capability=_clamp(fuzzy_agg(domains["capability"])),
        intent=_clamp(fuzzy_agg(domains["intent"])),
        instability=_clamp(fuzzy_agg(domains["instability"])),
        cost=_clamp(fuzzy_agg(domains["cost"])),
        logistics=_clamp(fuzzy_agg(domains["logistics"])),
        intent_profile=intent_profile
    )


def compute_escalation(domains: DomainIndex, temporal: List[TemporalIndicator], beliefs: List[Belief]) -> EscalationResult:
    base_score = (
        domains.capability * W_CAPABILITY +
        domains.intent * W_INTENT +
        domains.instability * W_INSTABILITY +
        domains.cost * W_COST
    )

    # Trend Bonus
    accelerating_count = sum(1 for t in temporal if t.trend_label == "accelerating")
    spike_count = sum(1 for t in temporal if t.is_spike)
    trend_bonus = min(TREND_BONUS_CAP, (accelerating_count * 0.05) + (spike_count * 0.08))
    temporal_spike_bonus = min(0.15, spike_count * 0.05)

    score = base_score + trend_bonus + temporal_spike_bonus
    
    res = EscalationResult()
    res.domain_indices = domains
    res.trend_bonus = trend_bonus
    res.temporal_spike_bonus = temporal_spike_bonus

    # Capability floor penalty
    if domains.capability < CAPABILITY_FLOOR:
        score *= 0.85
        res.capability_floor_applied = True

    # Mobilization and Logistics triggers
    for b in beliefs:
        if "MIL_MOBILIZATION" in b.signal_code and b.support_score > 0.60:
            score += 0.10
            res.mobilization_triggered = True
            res.mobilization_bonus = 0.10
        if "MIL_LOGISTICS" in b.signal_code and b.support_score > 0.60:
            score += 0.05
            res.logistics_triggered = True
            res.logistics_bonus = 0.05

    score = _clamp(score)
    res.escalation_score = round(score, 3)

    if score < 0.20:
        res.threat_level = "LOW"
    elif score < 0.40:
        res.threat_level = "MODERATE"
    elif score < 0.60:
        res.threat_level = "ELEVATED"
    elif score < 0.80:
        res.threat_level = "HIGH"
    else:
        res.threat_level = "CRITICAL"

    return res
