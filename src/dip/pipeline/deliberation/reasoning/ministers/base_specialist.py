import abc
import uuid
import logging
from typing import List

from dip.pipeline.deliberation.reasoning.schema import AgentMessage, MessageType, BeliefLedger, Belief
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus

logger = logging.getLogger("Layer4.BaseSpecialist")

class BaseSpecialist(abc.ABC):
    def __init__(self, name: str, mandate: str, message_bus: MessageBus):
        self.name = name
        self.mandate = mandate
        self.bus = message_bus
        self.inbox: List[AgentMessage] = []
        
        # Subscribe to messages directed at this agent or BROADCAST
        self.bus.subscribe_to_all(self._handle_incoming)

    async def _handle_incoming(self, message: AgentMessage):
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
        msg = AgentMessage(
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
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
            reasoning_summary=reasoning_summary
        )
        await self.bus.publish(msg)

    async def update_belief(self, state: str, prob: float):
        ledger = BeliefLedger(
            agent=self.name,
            beliefs=[Belief(state=state, probability=prob)]
        )
        self.bus.update_agent_belief(ledger)
        logger.info(f"[{self.name}] Belief updated: {state} = {prob}")
