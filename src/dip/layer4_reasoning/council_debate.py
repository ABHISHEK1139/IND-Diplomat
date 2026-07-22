"""
Council Debate Orchestrator
===========================
Orchestrates a debate between dynamic experts when their hypotheses
conflict. This replaces the hardcoded "concur/non-concur" logic from DIP 2.0
with an iterative multi-agent debate that leverages the World Model.
"""

import logging
import json
from typing import List

from dip.Config.config import config
from dip.layer10_telemetry.llm_tracer import tracer
from dip.layer3_world_model.world_model import WorldModel
from dip.layer4_reasoning.dynamic_experts import DynamicExpert
from dip.core.schema import MinisterHypothesisOutput
from dip.layer4_reasoning.dspy_signatures import DebateArbiter

try:
    import dspy
except ImportError:
    dspy = None

logger = logging.getLogger("Layer4.CouncilDebate")


class CouncilDebate:
    """
    Manages disagreements between experts, forcing them to find consensus
    or articulate irreconcilable uncertainty based on the World Model.
    """

    def __init__(self):
        self.model = config.LLM_MODEL

    async def resolve_conflicts(
        self, 
        world_model: WorldModel, 
        topic: str, 
        experts: List[DynamicExpert], 
        hypotheses: List[MinisterHypothesisOutput]
    ) -> MinisterHypothesisOutput:
        """
        Takes conflicting hypotheses and asks a Meta-Arbiter to synthesize 
        them or asks the experts to debate.
        For DIP 3.0, we use a single Tier 3 Arbiter pass to resolve the debate.
        """
        logger.info("Resolving hypothesis conflicts via Debate Arbiter.")
        
        # Format the debate context
        debate_context = f"Topic: {topic}\n\n"
        for i, hyp in enumerate(hypotheses):
            debate_context += f"Expert {i+1} ({hyp.minister}):\n"
            debate_context += f"- Confidence: {hyp.confidence}\n"
            debate_context += f"- Rationale: {hyp.rationale}\n"
            debate_context += f"- Predicted: {', '.join(hyp.predicted_signals)}\n\n"

        if not dspy:
            logger.error("dspy not found. Cannot run debate arbiter.")
            best = max(hypotheses, key=lambda h: h.confidence)
            return MinisterHypothesisOutput(
                minister="Fallback Consensus",
                confidence=best.confidence,
                predicted_signals=best.predicted_signals,
                rationale=f"Error: dspy not installed. Defaulted to highest confidence. {best.rationale}"
            )
            
        try:
            arbiter = dspy.ChainOfThought(DebateArbiter)
            result = arbiter(
                topic=topic,
                debate_context=debate_context
            )
            
            try:
                conf = float(result.confidence)
            except (ValueError, TypeError):
                conf = 0.5
                
            return MinisterHypothesisOutput(
                minister="Council Arbiter (DSPy)",
                predicted_signals=[s.strip() for s in result.predicted_signals.split(',')],
                matched_signals=[s.strip() for s in result.matched_signals.split(',')],
                missing_signals=[s.strip() for s in result.missing_signals.split(',')],
                confidence=conf,
                rationale=result.rationale
            )
        except Exception as e:
            logger.error(f"Council Debate failed: {e}")
            # Fallback to highest confidence
            best = max(hypotheses, key=lambda h: h.confidence)
            return MinisterHypothesisOutput(
                minister="Fallback Consensus",
                confidence=best.confidence,
                predicted_signals=best.predicted_signals,
                rationale=f"Debate failed, defaulted to highest confidence. {best.rationale}"
            )
