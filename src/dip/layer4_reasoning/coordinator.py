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
from dip.layer4_reasoning.dynamic_experts import DynamicExpertSpawner, DynamicExpert
from dip.layer4_reasoning.council_debate import CouncilDebate
from dip.layer3_world_model.world_model import WorldModel
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
        hypotheses = await asyncio.gather(*tasks)

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
async def run_council(session: CouncilSession, heuristic_baseline: List[Any] = None, baseline_confidence: bool = True, allow_rule_challenge: bool = True) -> List[Any]:
    coordinator = ReasoningCoordinator()
    
    # We use session.query as the topic
    topic = session.query
    domains = ["diplomacy", "military", "economy", "intelligence", "cyber", "legal", "infrastructure"]
    
    from dip.layer3_world_model.world_model import WorldModel
    world_model = getattr(session, 'world_model', None)
    if not world_model:
        world_model = WorldModel()
        
    hypotheses = await coordinator.run_council(world_model, topic, domains, heuristic_baseline)
    # We do NOT assign to session.hypotheses here; we return hypotheses
    return hypotheses

def _build_ministers():
    return []
