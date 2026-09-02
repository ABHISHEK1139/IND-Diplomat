"""
Debate Orchestrator (Phases 1-9 integrated)
============================================
State machine that controls the full deliberation cycle.

Integrates:
  - Phase 1: Message Bus
  - Phase 3: Evidence Bridge (injects real StateContext into agents)
  - Phase 4: Full debate loop (HYPOTHESIS → CHALLENGE → REBUTTAL → REVISION)
  - Phase 5: Contrarian Red Team
  - Phase 6: Verification Pipeline
  - Phase 7: Deterministic Gate
  - Phase 8: Groupthink Detection
  - Phase 9: Belief Revision tracking
"""

import asyncio
import logging
from enum import Enum
from typing import Dict, List, Optional

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
        self.gate_decision: str = "PENDING"
        self.groupthink_result: Optional[Dict] = None

    async def _wait_for_messages(self, message_types, expected_count: int, timeout_seconds: float = 60.0) -> bool:
        """Wait dynamically until expected number of messages arrive or timeout."""
        if not isinstance(message_types, (list, tuple, set)):
            message_types = [message_types]
            
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout_seconds:
            count = sum(
                1 for m in self.bus.debate_memory 
                if m.round >= self.round and m.message_type in message_types
            )
            if count >= expected_count:
                types_str = "/".join(t.value for t in message_types)
                logger.info(f"[Orchestrator] Received {count}/{expected_count} {types_str} messages.")
                return True
            await asyncio.sleep(0.3)
            
        types_str = "/".join(t.value for t in message_types)
        logger.warning(f"[Orchestrator] Timeout waiting for {types_str} messages. Proceeding.")
        return False

    async def advance_state(self):
        """State machine loop - one step per call."""
        if self.state == OrchestratorState.START:
            logger.info("[Orchestrator] Transitioning to EVIDENCE_READY")
            self.state = OrchestratorState.EVIDENCE_READY

        elif self.state == OrchestratorState.EVIDENCE_READY:
            logger.info("[Orchestrator] Broadcasting evidence to all agents.")
            self.state = OrchestratorState.INDEPENDENT_ANALYSIS

        elif self.state == OrchestratorState.INDEPENDENT_ANALYSIS:
            logger.info("[Orchestrator] Gathering independent hypotheses.")
            msg_id = f"sys_r{self.round}"
            msg = AgentMessage(
                message_id=msg_id,
                trace_id=self.bus.trace_id,
                round=self.round,
                sender="Orchestrator",
                receiver="BROADCAST",
                message_type=MessageType.EVIDENCE_REQUEST,
                claim="Produce initial independent hypotheses",
                reasoning_summary="Start of Phase 1.",
                signature=self.bus.auth.sign_message("Orchestrator", msg_id)
            )
            await self.bus.publish(msg)
            
            # Dynamically wait for all active non-contrarian ministers to respond
            expected_ministers = max(1, len([a for a in self.bus.registered_agents if a != "Contrarian"]))
            await self._wait_for_messages(MessageType.HYPOTHESIS, expected_count=expected_ministers, timeout_seconds=45.0)
            self.state = OrchestratorState.CROSS_EXAMINATION

        elif self.state == OrchestratorState.CROSS_EXAMINATION:
            logger.info("[Orchestrator] Cross-examination phase.")
            self.state = OrchestratorState.CONTRARIAN_CHALLENGE

        elif self.state == OrchestratorState.CONTRARIAN_CHALLENGE:
            logger.info("[Orchestrator] Red Team Contrarian challenge.")
            msg_id = f"sys_c{self.round}"
            msg = AgentMessage(
                message_id=msg_id,
                trace_id=self.bus.trace_id,
                round=self.round,
                sender="Orchestrator",
                receiver="BROADCAST",
                message_type=MessageType.EVIDENCE_REQUEST,
                claim="Contrarian challenge: attack the highest confidence hypothesis.",
                reasoning_summary="Start of Phase 5.",
                signature=self.bus.auth.sign_message("Orchestrator", msg_id)
            )
            await self.bus.publish(msg)
            
            # Dynamically wait for Contrarian to produce its challenge
            await self._wait_for_messages(MessageType.CHALLENGE, expected_count=1, timeout_seconds=30.0)
            self.state = OrchestratorState.REBUTTAL

        elif self.state == OrchestratorState.REBUTTAL:
            logger.info("[Orchestrator] Agent rebuttals and belief revision.")
            # Dynamically wait for challenged agent to produce its rebuttal or revision
            await self._wait_for_messages([MessageType.REBUTTAL, MessageType.REVISION], expected_count=1, timeout_seconds=30.0)
            self.state = OrchestratorState.CLAIM_VERIFICATION

        elif self.state == OrchestratorState.CLAIM_VERIFICATION:
            logger.info("[Orchestrator] Verification pipeline active.")
            from dip.pipeline.deliberation.reasoning.verification_pipeline import VerificationPipeline
            VerificationPipeline(self.bus)

            msg_id = f"sys_v{self.round}"
            msg = AgentMessage(
                message_id=msg_id,
                trace_id=self.bus.trace_id,
                round=self.round,
                sender="Orchestrator",
                receiver="BROADCAST",
                message_type=MessageType.VERIFICATION_REQUEST,
                claim="Verify all current hypotheses",
                reasoning_summary="Start of Phase 6.",
                signature=self.bus.auth.sign_message("Orchestrator", msg_id)
            )
            await self.bus.publish(msg)
            await asyncio.sleep(1)
            self.state = OrchestratorState.CONSENSUS_SYNTHESIS

        elif self.state == OrchestratorState.CONSENSUS_SYNTHESIS:
            logger.info("[Orchestrator] Synthesizing consensus.")

            # Phase 8: Groupthink Detection
            from dip.pipeline.deliberation.reasoning.groupthink_detector import GroupthinkDetector
            detector = GroupthinkDetector(self.bus)
            self.groupthink_result = detector.evaluate()

            if self.groupthink_result.get("warning"):
                logger.warning(
                    f"[Orchestrator] GROUPTHINK WARNING: risk={self.groupthink_result['groupthink_risk']}"
                )

            self.state = OrchestratorState.DETERMINISTIC_GATE

        elif self.state == OrchestratorState.DETERMINISTIC_GATE:
            logger.info("[Orchestrator] Running deterministic gates.")
            from dip.pipeline.deliberation.reasoning.deterministic_gate import DeterministicGate
            gate = DeterministicGate(self.bus)
            self.gate_decision = gate.evaluate()
            logger.info(f"[Orchestrator] Gate Decision: {self.gate_decision}")
            self.state = OrchestratorState.FINAL_ASSESSMENT

        elif self.state == OrchestratorState.FINAL_ASSESSMENT:
            logger.info("[Orchestrator] Final assessment produced. Halting debate.")

    async def run_debate(self):
        """Execute the full debate cycle."""
        await self.bus.start()

        while self.state != OrchestratorState.FINAL_ASSESSMENT:
            await self.advance_state()

        await asyncio.sleep(1)
        await self.bus.stop()

    def get_debate_summary(self) -> Dict:
        """Return a complete summary of the debate."""
        hypotheses = [m for m in self.bus.debate_memory if m.message_type == MessageType.HYPOTHESIS]
        challenges = [m for m in self.bus.debate_memory if m.message_type == MessageType.CHALLENGE]
        rebuttals = [m for m in self.bus.debate_memory if m.message_type == MessageType.REBUTTAL]
        revisions = [m for m in self.bus.debate_memory if m.message_type == MessageType.REVISION]

        return {
            "total_messages": len(self.bus.debate_memory),
            "hypotheses": len(hypotheses),
            "challenges": len(challenges),
            "rebuttals": len(rebuttals),
            "revisions": len(revisions),
            "gate_decision": self.gate_decision,
            "groupthink": self.groupthink_result,
            "agent_beliefs": {
                agent: ledgers[-1].beliefs[0].model_dump() if ledgers and ledgers[-1].beliefs else None
                for agent, ledgers in self.bus.agent_memory.items()
            },
        }
