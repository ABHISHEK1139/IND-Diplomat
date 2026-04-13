"""
Source-weighted evidence scoring.

Implements:
    evidence_weight = source_weight * recency * corroboration
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from contracts.observation import ObservationRecord
from Core.orchestrator.knowledge_port import knowledge_port
from engine.Layer3_StateModel.validation.freshness_model import freshness_scorer
from engine.Layer3_StateModel.validation.corroboration_engine import corroboration_engine


@dataclass
class WeightedEvidence:
    obs_id: str
    source_weight: float
    recency_weight: float
    corroboration_weight: float
    evidence_weight: float


class SourceWeighting:
    """
    Computes per-observation and aggregate evidence weights.
    """

    def score_observations(
        self,
        observations: List[ObservationRecord],
        reference_date: str,
    ) -> List[WeightedEvidence]:
        if not observations:
            return []

        freshness = {
            item.obs_id: item.clamped_score
            for item in freshness_scorer.score_batch(observations, reference_date)
        }
        corroboration = self._obs_corroboration_map(observations)

        scored: List[WeightedEvidence] = []
        for obs in observations:
            source_weight = knowledge_port.get_source_trust(obs.source)
            recency_weight = float(freshness.get(obs.obs_id, 0.1))
            corroboration_weight = float(corroboration.get(obs.obs_id, 0.2))
            evidence_weight = source_weight * recency_weight * corroboration_weight
            scored.append(
                WeightedEvidence(
                    obs_id=obs.obs_id,
                    source_weight=round(source_weight, 6),
                    recency_weight=round(recency_weight, 6),
                    corroboration_weight=round(corroboration_weight, 6),
                    evidence_weight=round(evidence_weight, 6),
                )
            )
        return scored

    def aggregate_score(
        self,
        observations: List[ObservationRecord],
        reference_date: str,
    ) -> float:
        weighted = self.score_observations(observations, reference_date)
        if not weighted:
            return 0.0
        return round(sum(item.evidence_weight for item in weighted) / len(weighted), 6)

    def _obs_corroboration_map(
        self,
        observations: List[ObservationRecord],
    ) -> Dict[str, float]:
        mapping: Dict[str, float] = {}
        for result in corroboration_engine.assess(observations):
            for obs_id in result.observation_ids:
                mapping[obs_id] = max(mapping.get(obs_id, 0.0), float(result.score))
        return mapping


source_weighting = SourceWeighting()

__all__ = ["SourceWeighting", "WeightedEvidence", "source_weighting"]
