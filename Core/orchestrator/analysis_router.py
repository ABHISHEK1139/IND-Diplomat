"""
Analysis Router — Signal Selector
==================================
Decides which signals and data sources to consult
based on the type of analysis requested.

This is NOT an LLM decision.
This is a routing table — deterministic and traceable.
"""

from typing import List, Dict
from enum import Enum


class AnalysisType(Enum):
    """Types of geopolitical analysis the system can perform."""
    WAR_RISK = "war_risk"
    ECONOMIC_PRESSURE = "economic_pressure"
    ESCALATION_FORECAST = "escalation_forecast"
    STABILITY_ASSESSMENT = "stability_assessment"
    SANCTIONS_IMPACT = "sanctions_impact"
    ALLIANCE_STATUS = "alliance_status"
    FULL_PROFILE = "full_profile"


# ══════════════════════════════════════════════════════════════════
# Routing Table
# ══════════════════════════════════════════════════════════════════
# For each analysis type, define which dimensions matter most
# and which data sources should be consulted.

ANALYSIS_ROUTES: Dict[AnalysisType, Dict] = {
    AnalysisType.WAR_RISK: {
        "primary_dimensions": ["military_pressure", "conflict_activity"],
        "secondary_dimensions": ["diplomatic_isolation"],
        "required_sources": ["GDELT", "SIPRI"],
        "optional_sources": ["ATOP"],
        "weight_override": {
            "conflict_activity": 0.40,
            "military_pressure": 0.35,
            "diplomatic_isolation": 0.15,
            "economic_stress": 0.05,
            "internal_instability": 0.05,
        },
        "description": "Assess probability of armed conflict",
    },

    AnalysisType.ECONOMIC_PRESSURE: {
        "primary_dimensions": ["economic_stress"],
        "secondary_dimensions": ["diplomatic_isolation"],
        "required_sources": ["WorldBank", "Sanctions"],
        "optional_sources": ["GDELT"],
        "weight_override": {
            "economic_stress": 0.50,
            "diplomatic_isolation": 0.20,
            "conflict_activity": 0.10,
            "military_pressure": 0.10,
            "internal_instability": 0.10,
        },
        "description": "Assess economic vulnerability and pressure",
    },

    AnalysisType.ESCALATION_FORECAST: {
        "primary_dimensions": [
            "conflict_activity", "military_pressure",
            "diplomatic_isolation", "economic_stress", "internal_stability"
        ],
        "secondary_dimensions": [],
        "required_sources": ["GDELT", "SIPRI", "WorldBank"],
        "optional_sources": ["V-Dem", "ATOP", "Sanctions"],
        "weight_override": None,  # Use default tension weights
        "description": "Full-spectrum escalation probability",
    },

    AnalysisType.STABILITY_ASSESSMENT: {
        "primary_dimensions": ["internal_stability", "economic_stress"],
        "secondary_dimensions": ["conflict_activity"],
        "required_sources": ["V-Dem", "WorldBank"],
        "optional_sources": ["GDELT", "Leaders"],
        "weight_override": {
            "internal_instability": 0.35,
            "economic_stress": 0.30,
            "conflict_activity": 0.15,
            "diplomatic_isolation": 0.10,
            "military_pressure": 0.10,
        },
        "description": "Assess internal regime stability",
    },

    AnalysisType.SANCTIONS_IMPACT: {
        "primary_dimensions": ["economic_stress", "diplomatic_isolation"],
        "secondary_dimensions": ["internal_stability"],
        "required_sources": ["Sanctions", "WorldBank"],
        "optional_sources": ["GDELT"],
        "weight_override": {
            "economic_stress": 0.40,
            "diplomatic_isolation": 0.30,
            "internal_instability": 0.15,
            "conflict_activity": 0.10,
            "military_pressure": 0.05,
        },
        "description": "Assess sanctions effectiveness",
    },

    AnalysisType.ALLIANCE_STATUS: {
        "primary_dimensions": ["diplomatic_isolation"],
        "secondary_dimensions": ["military_pressure", "conflict_activity"],
        "required_sources": ["ATOP", "GDELT"],
        "optional_sources": ["Sanctions"],
        "weight_override": {
            "diplomatic_isolation": 0.50,
            "military_pressure": 0.20,
            "conflict_activity": 0.15,
            "economic_stress": 0.10,
            "internal_instability": 0.05,
        },
        "description": "Assess alliance strength and isolation risk",
    },

    AnalysisType.FULL_PROFILE: {
        "primary_dimensions": [
            "conflict_activity", "military_pressure",
            "economic_stress", "diplomatic_isolation", "internal_stability"
        ],
        "secondary_dimensions": [],
        "required_sources": ["GDELT", "SIPRI", "WorldBank", "Sanctions", "V-Dem"],
        "optional_sources": ["ATOP", "Leaders"],
        "weight_override": None,  # Use default tension weights
        "description": "Complete country assessment across all dimensions",
    },
}


class AnalysisRouter:
    """
    Routes analysis requests to the correct signals and weights.

    Usage:
        router = AnalysisRouter()
        route = router.get_route(AnalysisType.WAR_RISK)
        required_sources = route["required_sources"]
    """

    def get_route(self, analysis_type: AnalysisType) -> Dict:
        """Get the routing configuration for an analysis type."""
        return ANALYSIS_ROUTES.get(analysis_type, ANALYSIS_ROUTES[AnalysisType.FULL_PROFILE])

    def classify_query(self, query: str) -> AnalysisType:
        """
        Map a natural language query to an analysis type.
        This is deterministic keyword matching, NOT LLM reasoning.
        """
        q = query.lower()

        if any(w in q for w in ["war", "attack", "invade", "military conflict"]):
            return AnalysisType.WAR_RISK
        elif any(w in q for w in ["sanction", "embargo", "trade ban"]):
            return AnalysisType.SANCTIONS_IMPACT
        elif any(w in q for w in ["economy", "recession", "inflation", "debt"]):
            return AnalysisType.ECONOMIC_PRESSURE
        elif any(w in q for w in ["escalat", "tension", "crisis"]):
            return AnalysisType.ESCALATION_FORECAST
        elif any(w in q for w in ["stab", "regime", "coup", "government"]):
            return AnalysisType.STABILITY_ASSESSMENT
        elif any(w in q for w in ["ally", "alliance", "partner", "isolat"]):
            return AnalysisType.ALLIANCE_STATUS
        else:
            return AnalysisType.FULL_PROFILE

    def get_available_sources(self) -> List[str]:
        """List all data sources the system knows about."""
        sources = set()
        for route in ANALYSIS_ROUTES.values():
            sources.update(route["required_sources"])
            sources.update(route["optional_sources"])
        return sorted(sources)


# Singleton
analysis_router = AnalysisRouter()
