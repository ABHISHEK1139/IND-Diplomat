"""
Unified Layer 1 -> Layer 2 -> Layer 3 orchestration.

This belongs to Core because it coordinates multiple layers and should not live
inside Layer-3 reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from contracts.observation import (
    ObservationDeduplicator,
    ObservationRecord,
    comtrade_state_to_observations,
    gdelt_events_to_observations,
    worldbank_state_to_observations,
)
from engine.Layer2_Knowledge.entity_registry import entity_registry
from engine.Layer2_Knowledge.multi_index import MultiIndexManager
from engine.Layer2_Knowledge.source_registry import source_registry
from engine.Layer2_Knowledge.translators.gdelt_translator import GDELTTranslator
from engine.Layer3_StateModel.relationship_state_builder import build_relationship_state
from engine.Layer3_StateModel.analysis_readiness import evaluate_analysis_readiness
from engine.Layer3_StateModel.evidence_gate import evidence_gate

try:
    from Core.debug.pipeline_trace import trace
except Exception:  # pragma: no cover - tracing is optional
    def trace(stage: str) -> None:
        return None


@dataclass
class Layer123Result:
    raw_event_count: int
    observation_count: int
    deduplicated_count: int
    indexed_count: int
    retrieved_count: int
    event_signal: Dict[str, Any]
    relationship_state: Dict[str, Any]
    analysis_readiness: Dict[str, Any] = field(default_factory=dict)
    evidence_gate: Dict[str, Any] = field(default_factory=dict)
    retrieved_documents: List[Dict[str, Any]] = field(default_factory=list)
    observations: List[ObservationRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_event_count": self.raw_event_count,
            "observation_count": self.observation_count,
            "deduplicated_count": self.deduplicated_count,
            "indexed_count": self.indexed_count,
            "retrieved_count": self.retrieved_count,
            "event_signal": self.event_signal,
            "relationship_state": self.relationship_state,
            "analysis_readiness": self.analysis_readiness,
            "evidence_gate": self.evidence_gate,
        }


class Layer123Pipeline:
    """Controller-style orchestrator for Layer1/Layer2/Layer3 integration tests."""

    def __init__(self, index_dir: Optional[str] = None):
        self._translator = GDELTTranslator()
        self._deduplicator = ObservationDeduplicator()
        self._index = MultiIndexManager(data_dir=index_dir)

    def run(
        self,
        *,
        raw_gdelt_events: List[Dict[str, Any]],
        country_a: str,
        country_b: str,
        start_date: str,
        end_date: str,
        query: Optional[str] = None,
        worldbank_state: Optional[Dict[str, Any]] = None,
        comtrade_state: Optional[Dict[str, Any]] = None,
    ) -> Layer123Result:
        trace("Layer1 ingestion")
        layer1_observations = gdelt_events_to_observations(
            raw_gdelt_events,
            source_confidence=source_registry.get_trust("gdelt"),
        )

        if worldbank_state:
            layer1_observations.extend(
                worldbank_state_to_observations(
                    worldbank_state,
                    source_confidence=source_registry.get_trust("world_bank"),
                )
            )

        if comtrade_state:
            layer1_observations.extend(
                comtrade_state_to_observations(
                    comtrade_state,
                    source_confidence=source_registry.get_trust("un_comtrade"),
                )
            )

        trace("Layer1 deduplication")
        deduped = self._deduplicator.process_batch(layer1_observations)
        normalized = self._normalize_observations(deduped)

        trace("Layer2 extraction and indexing")
        documents = [self._observation_to_document(obs) for obs in normalized]
        self._index.add_documents(documents)

        effective_query = query or f"{country_a} {country_b} sanctions military diplomacy"
        retrieved = self._index.search(query=effective_query, top_k=10)

        trace("Layer2 diplomatic signal translation")
        event_signal_obj = self._translator.translate(raw_gdelt_events)
        event_signal = {
            "source": event_signal_obj.source,
            "confidence": event_signal_obj.confidence,
            "timestamp": event_signal_obj.timestamp,
            "tension_score": event_signal_obj.tension_score,
            "goldstein_score": event_signal_obj.goldstein_score,
            "conflict_events": event_signal_obj.conflict_events,
            "cooperation_events": event_signal_obj.cooperation_events,
            "major_actors": event_signal_obj.major_actors,
        }

        trace("Layer3 state build")
        relationship = build_relationship_state(
            observations=normalized,
            country_a=country_a,
            country_b=country_b,
            start_date=start_date,
            end_date=end_date,
            reference_date=end_date,
        ).to_dict()

        trace("Layer3 readiness check")
        readiness = evaluate_analysis_readiness(
            country_state={
                "recent_activity_signals": len(retrieved),
                "signal_breakdown": {
                    "validation_confidence": {
                        "overall_score": relationship.get("confidence", {}).get("overall_score", 0.0)
                    }
                },
            },
            relationship_state=relationship,
            confidence=relationship.get("confidence", {}).get("overall_score", 0.0),
        ).to_dict()

        trace("Layer3 evidence gate")
        gate_result = evidence_gate.evaluate(
            documents=retrieved,
            required_evidence=["news_report", "official_statement"],
        ).to_dict()

        return Layer123Result(
            raw_event_count=len(raw_gdelt_events),
            observation_count=len(layer1_observations),
            deduplicated_count=len(normalized),
            indexed_count=len(documents),
            retrieved_count=len(retrieved),
            event_signal=event_signal,
            relationship_state=relationship,
            analysis_readiness=readiness,
            evidence_gate=gate_result,
            retrieved_documents=retrieved,
            observations=normalized,
        )

    def _normalize_observations(self, observations: List[ObservationRecord]) -> List[ObservationRecord]:
        normalized: List[ObservationRecord] = []
        for obs in observations:
            obs.actors = entity_registry.normalize_actors(obs.actors)
            if len(obs.actors) >= 2:
                obs.direction = f"{obs.actors[0]} -> {obs.actors[1]}"

            if obs.confidence_source is None:
                obs.confidence_source = source_registry.get_trust(obs.source)
            normalized.append(obs)
        return normalized

    def _observation_to_document(self, obs: ObservationRecord) -> Dict[str, Any]:
        content = (
            f"{obs.action_type.value} observed on {obs.event_date}: "
            f"{obs.direction or ', '.join(obs.actors)}"
        )
        return {
            "id": obs.obs_id,
            "content": content,
            "metadata": {
                "type": self._map_type(obs.action_type.value),
                "source": obs.source,
                "date": obs.event_date,
                "actors": obs.actors,
                "obs_id": obs.obs_id,
            },
        }

    def _map_type(self, action_type: str) -> str:
        if action_type in {"sanction", "trade_restriction", "trade_flow", "economic_indicator"}:
            return "report"
        if action_type in {"war", "violence", "threaten_military", "mobilize", "blockade"}:
            return "news"
        if action_type in {"diplomacy", "consultation", "cooperation", "statement", "trade_agreement"}:
            return "statement"
        return "news"


__all__ = ["Layer123Pipeline", "Layer123Result"]
