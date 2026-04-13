"""
Relationship State Builder - Structured pairwise assessment for Layer 3.

This module intentionally avoids any LLM usage. It computes a country-pair
state from observations, evidence drivers, and confidence components.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from contracts.observation import ActionType, ObservationRecord
from engine.Layer3_StateModel.validation.confidence_calculator import confidence_calculator


HOSTILE_ACTIONS = {
    ActionType.PRESSURE,
    ActionType.SANCTION,
    ActionType.TRADE_RESTRICTION,
    ActionType.EXPULSION,
    ActionType.THREATEN_MILITARY,
    ActionType.MOBILIZE,
    ActionType.BLOCKADE,
    ActionType.CYBER_ATTACK,
    ActionType.VIOLENCE,
    ActionType.WAR,
}

COOPERATIVE_ACTIONS = {
    ActionType.COOPERATION,
    ActionType.DIPLOMACY,
    ActionType.AID,
    ActionType.TRADE_AGREEMENT,
    ActionType.CONSULTATION,
}

ECONOMIC_ACTIONS = {
    ActionType.SANCTION,
    ActionType.TRADE_RESTRICTION,
    ActionType.TRADE_FLOW,
    ActionType.ECONOMIC_INDICATOR,
}


@dataclass
class RelationshipState:
    country_a: str
    country_b: str
    start_date: str
    end_date: str
    status: str
    tension_level: str
    tension_score: float
    main_drivers: List[str] = field(default_factory=list)
    supporting_evidence: List[str] = field(default_factory=list)
    confidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "countries": [self.country_a, self.country_b],
            "period": {"start": self.start_date, "end": self.end_date},
            "status": self.status,
            "tension_level": self.tension_level,
            "tension_score": round(self.tension_score, 4),
            "main_drivers": self.main_drivers,
            "supporting_evidence": self.supporting_evidence,
            "confidence": self.confidence,
        }


class RelationshipStateBuilder:
    """Builds a structured relationship state between two countries."""

    def assess(
        self,
        observations: List[ObservationRecord],
        country_a: str,
        country_b: str,
        start_date: str,
        end_date: str,
        reference_date: str | None = None,
    ) -> RelationshipState:
        a = country_a.upper()
        b = country_b.upper()
        pair_obs = [
            obs for obs in observations
            if start_date <= obs.event_date <= end_date
            and {a, b}.issubset({actor.upper() for actor in obs.actors})
        ]

        if not pair_obs:
            return RelationshipState(
                country_a=a,
                country_b=b,
                start_date=start_date,
                end_date=end_date,
                status="INSUFFICIENT_EVIDENCE",
                tension_level="unknown",
                tension_score=0.0,
                main_drivers=[],
                supporting_evidence=[],
                confidence=confidence_calculator.compute([]).to_dict(),
            )

        hostile = self._weighted_mean([obs for obs in pair_obs if obs.action_type in HOSTILE_ACTIONS])
        cooperative = self._weighted_mean([obs for obs in pair_obs if obs.action_type in COOPERATIVE_ACTIONS])
        economic = self._weighted_mean([obs for obs in pair_obs if obs.action_type in ECONOMIC_ACTIONS])

        tension_score = (hostile * 0.60) + (economic * 0.25) + ((1.0 - cooperative) * 0.15)
        tension_score = max(0.0, min(1.0, tension_score))

        if tension_score >= 0.75:
            level = "critical"
        elif tension_score >= 0.55:
            level = "high"
        elif tension_score >= 0.35:
            level = "moderate"
        elif tension_score >= 0.15:
            level = "low"
        else:
            level = "minimal"

        drivers = self._top_drivers(pair_obs)
        evidence_ids = [
            obs.obs_id
            for obs in sorted(
                pair_obs,
                key=lambda item: (item.confidence * item.intensity),
                reverse=True,
            )[:10]
        ]

        report = confidence_calculator.compute(pair_obs, reference_date=reference_date or end_date)
        return RelationshipState(
            country_a=a,
            country_b=b,
            start_date=start_date,
            end_date=end_date,
            status="OK",
            tension_level=level,
            tension_score=tension_score,
            main_drivers=drivers,
            supporting_evidence=evidence_ids,
            confidence=report.to_dict(),
        )

    def _weighted_mean(self, observations: List[ObservationRecord]) -> float:
        if not observations:
            return 0.0
        weights = [max(0.01, obs.confidence) for obs in observations]
        numerator = sum(obs.intensity * weight for obs, weight in zip(observations, weights))
        denominator = sum(weights)
        return numerator / denominator if denominator > 0 else 0.0

    def _top_drivers(self, observations: List[ObservationRecord]) -> List[str]:
        counts: Dict[str, int] = {}
        for obs in observations:
            key = obs.action_type.value
            counts[key] = counts.get(key, 0) + 1
        ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        return [name for name, _ in ordered[:5]]


relationship_state_builder = RelationshipStateBuilder()


def build_relationship_state(
    observations: List[ObservationRecord],
    country_a: str,
    country_b: str,
    start_date: str,
    end_date: str,
    reference_date: str | None = None,
) -> RelationshipState:
    return relationship_state_builder.assess(
        observations=observations,
        country_a=country_a,
        country_b=country_b,
        start_date=start_date,
        end_date=end_date,
        reference_date=reference_date,
    )


__all__ = [
    "RelationshipState",
    "RelationshipStateBuilder",
    "relationship_state_builder",
    "build_relationship_state",
]
