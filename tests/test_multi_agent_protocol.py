import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.pipeline.deliberation.reasoning.debate_orchestrator import DebateOrchestrator
from dip.pipeline.deliberation.reasoning.ministers.base_specialist import BaseSpecialist
from dip.pipeline.deliberation.reasoning.schema import AgentMessage, MessageType

class MockMinister(BaseSpecialist):
    async def process_message(self, message: AgentMessage):
        if message.sender == "Orchestrator":
            print(f"[{self.name}] Received Orchestrator Trigger. Formulating hypothesis...")
            await self.send_message(
                receiver="BROADCAST",
                message_type=MessageType.HYPOTHESIS,
                claim=f"{self.name} believes escalation is imminent.",
                round_num=1,
                state="ACTIVE_CONFLICT",
                probability=0.75,
                confidence=0.8
            )
            await self.update_belief("ACTIVE_CONFLICT", 0.75)
        elif message.message_type == MessageType.HYPOTHESIS and message.sender != self.name:
            print(f"[{self.name}] Read Hypothesis from {message.sender}: {message.claim}")

async def run_protocol_test():
    print("\n--- Booting IND-Diplomat Structured Debate Protocol ---")
    bus = MessageBus()
    
    # Register agents
    security = MockMinister("Security Minister", "Military Capability", bus)
    diplomatic = MockMinister("Diplomatic Minister", "Negotiations", bus)
    
    orchestrator = DebateOrchestrator(bus)
    
    # Run the debate state machine
    await orchestrator.run_debate()
    
    print("\n--- Debate Memory Trace ---")
    for msg in bus.debate_memory:
        print(f"Msg ID: {msg.message_id} | {msg.sender} -> {msg.receiver} | {msg.message_type.value} | {msg.claim}")

    print("\n--- Agent Belief Ledger ---")
    for agent, ledgers in bus.agent_memory.items():
        print(f"{agent}: {ledgers[-1].beliefs[0].state} = {ledgers[-1].beliefs[0].probability}")

if __name__ == "__main__":
    asyncio.run(run_protocol_test())
