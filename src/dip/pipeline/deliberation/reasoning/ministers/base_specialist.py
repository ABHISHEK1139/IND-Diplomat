"""
Base Specialist (Phase 2/3/4/9)
================================
Abstract base for all 7 analytical specialists.

Key capabilities:
  - Consumes real StateContext evidence via the EvidenceBridge
  - Maintains a BeliefLedger with historical trajectory
  - Can issue EVIDENCE_REQUEST when data is weak
  - Revises beliefs in response to CHALLENGEs (Phase 4/9)
  - Records belief revision reasons for temporal memory (Phase 9)
"""

import abc
import uuid
import logging
from typing import List, Dict, Optional

from dip.pipeline.deliberation.reasoning.schema import (
    AgentMessage, MessageType, BeliefLedger, Belief as SchemaBelief
)
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.pipeline.deliberation.reasoning.belief_revision import BeliefTrajectory, BeliefSnapshot

logger = logging.getLogger("Layer4.BaseSpecialist")


class BaseSpecialist(abc.ABC):
    """
    Abstract base for all 7 analytical specialists.
    Each specialist has:
      - A name and analytical mandate
      - A connection to the Message Bus
      - A local belief trajectory (Phase 9)
      - An evidence context built from the EvidenceBridge (Phase 3)
    """

    def __init__(self, name: str, mandate: str, message_bus: MessageBus):
        self.name = name
        self.mandate = mandate
        self.bus = message_bus
        self.inbox: List[AgentMessage] = []

        # Phase 3: Agent-specific evidence context
        self.evidence_context: str = ""
        self.my_evidence_ids: List[str] = []

        # Phase 9: Local belief trajectory
        self.belief_trajectory = BeliefTrajectory()

        # Register with message bus
        self.bus.register_agent(self.name)

        # Subscribe to messages directed at this agent or BROADCAST
        self.bus.subscribe_to_all(self._handle_incoming)

    def set_evidence_context(self, context: str, evidence_ids: List[str]):
        """Set the evidence context built by EvidenceBridge (Phase 3)."""
        self.evidence_context = context
        self.my_evidence_ids = evidence_ids

    async def _handle_incoming(self, message: AgentMessage):
        """Route incoming messages. Only process messages addressed to this agent or BROADCAST."""
        if message.receiver == self.name or message.receiver == "BROADCAST":
            self.inbox.append(message)
            await self.process_message(message)

    @abc.abstractmethod
    async def process_message(self, message: AgentMessage):
        """Handle incoming messages and decide whether to reply."""
        pass

    async def send_message(
        self,
        receiver: str,
        message_type: MessageType,
        claim: str,
        round_num: int,
        state: str = None,
        probability: float = None,
        confidence: float = None,
        evidence_ids: List[str] = None,
        counter_evidence: List[str] = None,
        reasoning_summary: str = ""
    ):
        """Publish a structured message to the bus."""
        msg_id = f"msg_{uuid.uuid4().hex[:8]}"
        msg = AgentMessage(
            message_id=msg_id,
            trace_id=self.bus.trace_id,
            round=round_num,
            sender=self.name,
            receiver=receiver,
            message_type=message_type,
            claim=claim,
            state=state,
            probability=probability,
            confidence=confidence,
            evidence_ids=evidence_ids or [],
            counter_evidence=counter_evidence or [],
            reasoning_summary=reasoning_summary,
            signature=self.bus.auth.sign_message(self.name, msg_id)
        )
        await self.bus.publish(msg)

    async def update_belief(self, state: str, prob: float, reason: str = "",
                            evidence_ids: Optional[List[str]] = None, round_num: int = 0):
        """
        Update this agent's belief and record the revision in the trajectory.
        This is Phase 9: every belief change records WHY it changed.
        """
        # Update bus-level belief ledger
        ledger = BeliefLedger(
            agent=self.name,
            beliefs=[SchemaBelief(state=state, probability=prob)]
        )
        self.bus.update_agent_belief(ledger)

        # Record in local trajectory (Phase 9)
        self.belief_trajectory.record(
            agent=self.name,
            state=state,
            probability=prob,
            reason=reason,
            evidence_ids=evidence_ids or [],
            round_num=round_num,
        )

        logger.info(f"[{self.name}] Belief updated: {state} = {prob:.3f} (reason: {reason})")

    async def request_evidence(self, query: str, round_num: int):
        """Issue an EVIDENCE_REQUEST when data is weak (Phase 3)."""
        await self.send_message(
            receiver="Orchestrator",
            message_type=MessageType.EVIDENCE_REQUEST,
            claim=f"RFI from {self.name}: {query}",
            round_num=round_num,
            reasoning_summary=f"{self.name} requires additional evidence: {query}"
        )
        logger.info(f"[{self.name}] Issued EVIDENCE_REQUEST: {query}")

    async def perform_web_search(self, query: str, max_results: int = 3) -> List[str]:
        """Perform live autonomous internet search via ResilientWebSurfer.
        
        Fetches live OSINT, injects new EvidenceNodes into the MessageBus,
        and appends new findings to this agent's private context.
        """
        try:
            from dip.pipeline.collection.research.retrieval.web_surfer import ResilientWebSurfer
            surfer = ResilientWebSurfer()
            observations = await surfer.search(query=query, max_results=max_results)
            new_snippets = []
            for obs in observations:
                snippet = f"[{self.name} Web Search] {obs.content}"
                new_snippets.append(snippet)
                ev_id = f"EV_WEB_{uuid.uuid4().hex[:6]}"
                self.bus.add_evidence(EvidenceNode(
                    evidence_id=ev_id,
                    observation_id=obs.source_id or "WEB",
                    source="LiveWebSearch",
                    reliability=0.80,
                    content=obs.content,
                    timestamp=datetime.now(timezone.utc).isoformat()
                ))
                self.my_evidence_ids.append(ev_id)
            if new_snippets:
                self.evidence_context += "\n" + "\n".join(new_snippets)
                logger.info(f"[{self.name}] Live web search for '{query}' found {len(new_snippets)} new facts.")
            return new_snippets
        except Exception as e:
            logger.warning(f"[{self.name}] Live web search failed: {e}")
            return []

    def get_belief_summary(self) -> Dict:
        """Return this agent's belief trajectory summary (Phase 9)."""
        return self.belief_trajectory.summary().get(self.name, {})
