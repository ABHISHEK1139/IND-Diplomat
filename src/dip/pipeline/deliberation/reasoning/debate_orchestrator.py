import asyncio
import logging
from enum import Enum

from dip.pipeline.deliberation.reasoning.schema import MessageType, AgentMessage
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus

logger = logging.getLogger("Layer4.DebateOrchestrator")

class OrchestratorState(Enum):
    START = "START"
    EVIDENCE_READY = "EVIDENCE_READY"
    INDEPENDENT_ANALYSIS = "INDEPENDENT_ANALYSIS"
    CROSS_EXAMINATION = "CROSS_EXAMINATION"
    CONTRARIAN_CHALLENGE = "CONTRARIAN_CHALLENGE"
    REBUTTAL = "REBUTTAL"
    CLAIM_VERIFICATION = "CLAIM_VERIFICATION"
    CONSENSUS_SYNTHESIS = "CONSENSUS_SYNTHESIS"
    DETERMINISTIC_GATE = "DETERMINISTIC_GATE"
    FINAL_ASSESSMENT = "FINAL_ASSESSMENT"

class DebateOrchestrator:
    """
    Traffic controller for the Debate Protocol.
    Determines who speaks, when, and enforces the state machine.
    """
    def __init__(self, message_bus: MessageBus):
        self.bus = message_bus
        self.state = OrchestratorState.START
        self.round = 1

    async def advance_state(self):
        """State machine loop."""
        if self.state == OrchestratorState.START:
            logger.info("[Orchestrator] Transitioning to EVIDENCE_READY")
            self.state = OrchestratorState.EVIDENCE_READY
            
        elif self.state == OrchestratorState.EVIDENCE_READY:
            logger.info("[Orchestrator] Broadcasting evidence to all agents.")
            self.state = OrchestratorState.INDEPENDENT_ANALYSIS
            
        elif self.state == OrchestratorState.INDEPENDENT_ANALYSIS:
            logger.info("[Orchestrator] Gathering independent hypotheses.")
            msg = AgentMessage(
                message_id=f"sys_r{self.round}",
                round=self.round,
                sender="Orchestrator",
                receiver="BROADCAST",
                message_type=MessageType.EVIDENCE_REQUEST,
                claim="Produce initial independent hypotheses",
                reasoning_summary="Start of Phase 1."
            )
            await self.bus.publish(msg)
            await asyncio.sleep(2)
            self.state = OrchestratorState.CROSS_EXAMINATION
            
        elif self.state == OrchestratorState.CROSS_EXAMINATION:
            logger.info("[Orchestrator] Cross-examination phase.")
            self.state = OrchestratorState.CONTRARIAN_CHALLENGE
            
        elif self.state == OrchestratorState.CONTRARIAN_CHALLENGE:
            logger.info("[Orchestrator] Red Team Contrarian challenge.")
            self.state = OrchestratorState.REBUTTAL
            
        elif self.state == OrchestratorState.REBUTTAL:
            logger.info("[Orchestrator] Agent rebuttals and belief revision.")
            self.state = OrchestratorState.CLAIM_VERIFICATION
            
        elif self.state == OrchestratorState.CLAIM_VERIFICATION:
            logger.info("[Orchestrator] Verification pipeline active.")
            self.state = OrchestratorState.CONSENSUS_SYNTHESIS
            
        elif self.state == OrchestratorState.CONSENSUS_SYNTHESIS:
            logger.info("[Orchestrator] Synthesizing consensus.")
            self.state = OrchestratorState.DETERMINISTIC_GATE
            
        elif self.state == OrchestratorState.DETERMINISTIC_GATE:
            logger.info("[Orchestrator] Running deterministic gates.")
            self.state = OrchestratorState.FINAL_ASSESSMENT
            
        elif self.state == OrchestratorState.FINAL_ASSESSMENT:
            logger.info("[Orchestrator] Final assessment produced. Halting debate.")

    async def run_debate(self):
        await self.bus.start()
        
        while self.state != OrchestratorState.FINAL_ASSESSMENT:
            await self.advance_state()
            
        await asyncio.sleep(1)
        await self.bus.stop()
