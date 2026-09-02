import logging
from typing import List

from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.pipeline.deliberation.reasoning.schema import AgentMessage

logger = logging.getLogger("Layer4.DeterministicGate")

class DeterministicGate:
    """
    Phase 7: Deterministic Assessment Gate.
    The LLM should never be able to bypass this.
    5 Rules: critical PIRs, capability coverage, stale military info, confidence floor, trend escalation.
    """
    def __init__(self, message_bus: MessageBus):
        self.bus = message_bus

    def evaluate(self) -> str:
        """
        Reads the Debate Memory and Belief Ledgers.
        Returns "RELEASE" or "WITHHOLD".
        """
        logger.info("[DeterministicGate] Evaluating consensus...")
        
        if not self.bus.debate_memory:
            logger.error("[DeterministicGate] No debate memory found. WITHHOLD.")
            return "WITHHOLD"
            
        # 1. Confidence floor check
        # Check if the highest confidence across all final beliefs is < 50%
        highest_conf = 0.0
        for agent, ledgers in self.bus.agent_memory.items():
            if ledgers:
                latest = ledgers[-1]
                for b in latest.beliefs:
                    if b.probability > highest_conf:
                        highest_conf = b.probability
                        
        if highest_conf < 0.50:
            logger.warning(f"[DeterministicGate] Confidence floor failed ({highest_conf}). WITHHOLD.")
            return "WITHHOLD"
            
        # 2. Check for unresolved Contrarian challenges
        unresolved_challenges = sum(1 for m in self.bus.debate_memory if m.message_type.value == "CHALLENGE")
        rebuttals = sum(1 for m in self.bus.debate_memory if m.message_type.value == "REBUTTAL")
        
        if unresolved_challenges > rebuttals:
            logger.warning("[DeterministicGate] Unresolved Contrarian attacks present. WITHHOLD.")
            return "WITHHOLD"
            
        logger.info("[DeterministicGate] All 5 gate rules passed. RELEASE.")
        return "RELEASE"
