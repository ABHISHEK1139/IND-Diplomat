"""
Signal-to-collection query mappings for investigation tasking.
"""

from __future__ import annotations


SIGNAL_COLLECTION_MAP = {
    # Core part-3 mappings
    "SIG_MIL_ESCALATION": "military movements OR troop mobilization OR airbase activity",
    "SIG_CYBER_ACTIVITY": "cyber attack OR ddos OR infrastructure intrusion OR malware campaign",
    "SIG_DIP_HOSTILITY": "diplomatic protest OR ambassador summoned OR hostile statement",
    "SIG_ECON_PRESSURE": "sanctions OR export ban OR trade restriction",
    "SIG_ALLIANCE_SHIFT": "military pact OR defense agreement OR joint exercises",
    "SIG_FORCE_POSTURE": "forward deployment OR force posture change OR elevated readiness",
    "SIG_LOGISTICS_PREP": "military logistics convoy OR supply staging OR fuel movement",
    "SIG_DECEPTION_ACTIVITY": "military deception OR feint exercises OR information operations",

    # Compact ontology aliases
    "SIG_MIL_MOBILIZATION": "military movements OR troop mobilization OR airbase activity",
    "SIG_FORCE_CONCENTRATION": "troop concentration OR forward deployment OR border buildup",
    "SIG_LOGISTICS_SURGE": "military logistics convoy OR fuel movement OR supply transfer",
    "SIG_EXERCISE_ESCALATION": "military drills OR exercise escalation OR live-fire activity",
    "SIG_CYBER_PREPARATION": "cyber attack OR infrastructure intrusion OR malware campaign",
    "SIG_NEGOTIATION_BREAKDOWN": "diplomatic talks suspended OR negotiation collapse",
    "SIG_ALLIANCE_ACTIVATION": "military pact OR defense agreement OR joint exercises",
    "SIG_ECONOMIC_PRESSURE": "sanctions OR export ban OR trade restriction",
    "SIG_SANCTIONS_ACTIVE": "sanctions enforcement OR export controls OR trade restrictions",
    "SIG_INTERNAL_INSTABILITY": "civil unrest OR protest surge OR internal security alerts",
    "SIG_REGIME_STABLE": "regime stability indicators OR domestic stabilization measures",

    # Canonical ontology aliases
    "SIG_MIL_LOGISTICS_SURGE": "military logistics convoy OR fuel movement OR supply transfer",
    "SIG_MIL_EXERCISE_ESCALATION": "military drills OR exercise escalation OR live-fire activity",
    "SIG_MIL_FORWARD_DEPLOYMENT": "troop concentration OR forward deployment OR border buildup",
    "SIG_MIL_BORDER_CLASHES": "border clashes OR skirmishes OR engagement reports",
    "SIG_DIP_HOSTILE_RHETORIC": "diplomatic protest OR ambassador summoned OR hostile statement",
    "SIG_DIP_CHANNEL_CLOSURE": "diplomatic talks suspended OR negotiation collapse",
    "SIG_DIP_ALLIANCE_COORDINATION": "military pact OR defense agreement OR joint exercises",
    "SIG_ECO_PRESSURE_HIGH": "sanctions OR export ban OR trade restriction",
    "SIG_ECO_SANCTIONS_ACTIVE": "sanctions enforcement OR export controls OR trade restrictions",
    "SIG_DOM_REGIME_INSTABILITY": "civil unrest OR protest surge OR internal security alerts",
    "SIG_DOM_CIVIL_UNREST": "civil unrest OR protest surge OR internal security alerts",
    "SIG_CAP_CYBER_PREPARATION": "cyber attack OR infrastructure intrusion OR malware campaign",

    # Legacy aliases retained for compatibility and tests
    "troop_staging": "troop buildup near border",
    "logistics_movement": "military fuel convoy movement",
    "supply_stockpiling": "ammunition storage activity",
    "command_relocation": "military command headquarters relocation",
    "aggressive_rhetoric": "official hostile rhetoric statements",
    "sanctions_pressure": "sanctions enforcement indicators",
    "economic_pressure_high": "economic pressure escalation signals",
    "domestic_unrest": "domestic unrest protest escalation indicators",
}

# Backward-compatible name used by existing imports.
SIGNAL_TO_QUERY = SIGNAL_COLLECTION_MAP


__all__ = ["SIGNAL_COLLECTION_MAP", "SIGNAL_TO_QUERY"]
