"""
Coordinator
===========
Wires the DynamicExpertSpawner and CouncilDebate modules together.
1. Spawns domain-specific experts.
2. Queries the World Model for context.
3. Has experts independently generate hypotheses.
4. Detects conflicts.
5. Runs the Debate Arbiter if conflicts exist.
"""

import asyncio
import logging
from typing import List, Tuple, Dict, Any

from .council_session import CouncilSession
from dip.pipeline.deliberation.reasoning.dynamic_experts import DynamicExpertSpawner, DynamicExpert
from dip.pipeline.deliberation.reasoning.council_debate import CouncilDebate
from dip.pipeline.world_model.world.world_model import WorldModel
from dip.core.schema import MinisterHypothesisOutput

logger = logging.getLogger("Layer4.Coordinator")

CONFLICT_THRESHOLD = 0.3  # Stricter for dynamic experts


class ReasoningCoordinator:
    """
    Orchestrates the Multi-Expert Reasoning Council.
    """
    def __init__(self):
        self.spawner = DynamicExpertSpawner()
        self.debater = CouncilDebate()

    def _detect_conflicts(self, hypotheses: List[MinisterHypothesisOutput]) -> bool:
        """
        Detects if there is significant disagreement between experts.
        """
        if len(hypotheses) < 2:
            return False

        confidences = [h.confidence for h in hypotheses if h.confidence is not None]
        if not confidences:
            return False
            
        spread = max(confidences) - min(confidences)
        if spread > CONFLICT_THRESHOLD:
            logger.warning(f"Confidence spread ({spread:.2f}) exceeds threshold. Conflict detected.")
            return True
            
        # We could also do semantic conflict detection on the predicted_signals here using DeBERTa
        return False

    async def run_council(
        self, 
        world_model: WorldModel, 
        topic: str, 
        domains: List[str],
        heuristic_baseline: List[Any] = None
    ) -> List[MinisterHypothesisOutput]:
        """
        Executes the reasoning phase.
        """
        # 1. Spawn Experts
        experts = await self.spawner.spawn_experts(topic, domains, heuristic_baseline)
        
        if not experts:
            logger.error("No experts spawned. Returning empty hypothesis.")
            return []

        # 2. Independent Analysis (Parallel)
        tasks = [expert.analyze(world_model, topic, heuristic_baseline) for expert in experts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        hypotheses = [res for res in results if not isinstance(res, Exception)]

        # 3. Detect Conflicts
        all_hypotheses = list(hypotheses)
        if heuristic_baseline:
            all_hypotheses.extend(heuristic_baseline)
        has_conflict = self._detect_conflicts(all_hypotheses)

        # 4. Resolve via Debate if needed
        final_hypotheses = list(hypotheses)
        if has_conflict:
            consensus = await self.debater.resolve_conflicts(world_model, topic, experts, all_hypotheses)
            final_hypotheses.append(consensus)
            
        return final_hypotheses
from dip.pipeline.deliberation.reasoning.ministers import (
    SecurityMinister,
    StrategyMinister,
    DiplomacyMinister,
    DomesticMinister,
    EconomicMinister,
    AllianceMinister,
    ContrarianMinister,
)

def _build_ministers() -> List[Any]:
    return [
        SecurityMinister(),
        StrategyMinister(),
        DiplomacyMinister(),
        DomesticMinister(),
        EconomicMinister(),
        AllianceMinister(),
        ContrarianMinister(),
    ]

async def run_council(
    session: CouncilSession,
    heuristic_baseline: List[Any] = None,
    baseline_confidence: bool = True,
    allow_rule_challenge: bool = True
) -> CouncilSession:
    """Convenience entry point for convening the minister council."""
    import os
    force_heuristic = os.getenv("FORCE_MINISTER_HEURISTIC", "0") == "1"
    
    ministers = _build_ministers()
    hypotheses: List[Any] = []
    
    # 1. Run core ministers on StateContext
    if getattr(session, "state_context", None) is not None:
        for minister in ministers:
            try:
                h = await minister.produce_hypothesis(session.state_context)
                hypotheses.append(h)
                if hasattr(session, "evidence_log") and getattr(h, "matched_signals", None):
                    session.evidence_log.extend(h.matched_signals)
                if hasattr(session, "missing_signals") and getattr(h, "missing_signals", None):
                    session.missing_signals.extend(h.missing_signals)
            except Exception as e:
                logger.debug(f"Minister {getattr(minister, 'minister_name', 'Unknown')} error: {e}")

    # 2. Run Dynamic Experts if LLM enabled
    if not force_heuristic:
        try:
            coordinator = ReasoningCoordinator()
            topic = session.query
            domains = ["diplomacy", "military", "economy", "intelligence", "cyber", "legal", "infrastructure"]
            
            world_model = getattr(session, 'world_model', None)
            if not world_model:
                world_model = WorldModel()
                
            dynamic_hyps = await coordinator.run_council(world_model, topic, domains, heuristic_baseline or hypotheses)
            if dynamic_hyps:
                hypotheses.extend(dynamic_hyps)
        except Exception as e:
            logger.debug(f"Dynamic experts run failed: {e}")

    # 3. Detect conflicts
    if hypotheses:
        confidences = [h.confidence for h in hypotheses if getattr(h, "confidence", None) is not None]
        if confidences and (max(confidences) - min(confidences) > CONFLICT_THRESHOLD):
            if hasattr(session, "conflicts") and "High minister disagreement" not in session.conflicts:
                session.conflicts.append("High minister disagreement")

    session.hypotheses = hypotheses
    return session

