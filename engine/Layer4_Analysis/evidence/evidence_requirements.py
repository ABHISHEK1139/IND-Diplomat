"""
Canonical evidence requirements for Layer-4 hypothesis testing.
"""

from __future__ import annotations

from typing import Dict, List


HYPOTHESIS_REQUIREMENTS: Dict[str, List[str]] = {
    "invasion_preparation": [
        "troop_staging",
        "logistics_movement",
        "supply_stockpiling",
        "command_relocation",
    ],
    "escalation_ladder_management": [
        "military_exercises",
        "aggressive_rhetoric",
        "diplomatic_messages",
        "media_signaling",
    ],
    "coercive_bargaining": [
        "military_exercises",
        "aggressive_rhetoric",
        "diplomatic_messages",
        "media_signaling",
    ],
    "domestic_diversion": [
        "domestic_unrest",
        "nationalist_speeches",
        "external_threat_narrative",
    ],
    "economic_compellence": [
        "sanctions_pressure",
        "economic_pressure_high",
        "coercive_trade_actions",
        "trade_dependency_leverage",
    ],
    "regional_balancing": [
        "alliance_activation",
        "joint_exercises",
        "diplomatic_messages",
        "regional_deterrence_posture",
    ],
    # Step 5: Risk Requirements
    "stable_deterrence": [
        "de_escalation_rhetoric",
        "diplomatic_channel_open",
        "military_exercise",
    ],
    "escalation_risk": [
        "border_flare_up",
        "aggressive_rhetoric",
        "logistics_movement",
    ],
    "internal_instability": [
        "civil_unrest",
        "domestic_instability",
        "protest_pressure",
    ],
    "rising_tension": [
        "aggressive_rhetoric",
        "troop_staging",
        "diplomatic_channel_closure",
    ],
}


HYPOTHESIS_ALIASES: Dict[str, str] = {
    "invasion": "invasion_preparation",
    "invasion_preparation": "invasion_preparation",
    "coercive_signaling": "coercive_bargaining",
    "coercive_bargaining": "coercive_bargaining",
    "regime_distraction": "domestic_diversion",
    "domestic_diversion": "domestic_diversion",
    "economic_pressure": "economic_compellence",
    "economic_compellence": "economic_compellence",
    "escalation_ladder_management": "escalation_ladder_management",
    "regional_balancing": "regional_balancing",
}


def canonical_hypothesis_name(name: str) -> str:
    token = str(name or "").strip().lower().replace("-", "_").replace(" ", "_")
    token = "".join(ch for ch in token if ch.isalnum() or ch == "_")
    if token in HYPOTHESIS_REQUIREMENTS:
        return token
    return HYPOTHESIS_ALIASES.get(token, token)


def requirements_for(hypothesis: str) -> List[str]:
    canonical = canonical_hypothesis_name(hypothesis)
    return list(HYPOTHESIS_REQUIREMENTS.get(canonical, []))


__all__ = [
    "HYPOTHESIS_REQUIREMENTS",
    "HYPOTHESIS_ALIASES",
    "canonical_hypothesis_name",
    "requirements_for",
]

