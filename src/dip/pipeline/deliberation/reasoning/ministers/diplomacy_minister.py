import json
from typing import List

from dip.pipeline.deliberation.reasoning.schema import AgentMessage, MessageType
from dip.pipeline.deliberation.reasoning.ministers.base_specialist import BaseSpecialist
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.telemetry.llm_tracer import tracer
from dip.core.Config.config import config
from dip.core.json_utils import strip_markdown_json

class DiplomacySpecialist(BaseSpecialist):
    def __init__(self, message_bus: MessageBus):
        mandate = (
            "Focus: treaties, negotiations, demarches, public rhetoric vs private signaling. "
            "Answer: 'Is this diplomatic posturing or genuine negotiation?'"
        )
        super().__init__("Diplomacy", mandate, message_bus)

    async def process_message(self, message: AgentMessage):
        if message.message_type == MessageType.EVIDENCE_REQUEST and message.sender == "Orchestrator":
            await self._formulate_hypothesis(message)

    async def _formulate_hypothesis(self, trigger_msg: AgentMessage):
        prompt = f"""You are the Diplomacy Agent. Mandate: {self.mandate}
Analyze the global evidence memory. Respond in JSON:
{{
    "claim": "Your main hypothesis",
    "state": "ACTIVE_CONFLICT",
    "probability": 0.40,
    "confidence": 0.80,
    "reasoning_summary": "Explanation based on diplomatic indicators."
}}"""
        try:
            response = await tracer.acompletion(
                layer="Layer4_Diplomacy",
                model=config.LLM_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            data = json.loads(strip_markdown_json(response.choices[0].message.content))
            await self.update_belief(data.get("state", "UNKNOWN"), data.get("probability", 0.5))
            await self.send_message(
                receiver="BROADCAST",
                message_type=MessageType.HYPOTHESIS,
                claim=data.get("claim", ""),
                round_num=trigger_msg.round,
                state=data.get("state"),
                probability=data.get("probability"),
                confidence=data.get("confidence"),
                reasoning_summary=data.get("reasoning_summary", "")
            )
        except Exception:
            pass
