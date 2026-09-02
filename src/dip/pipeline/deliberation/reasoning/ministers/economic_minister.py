import json
from typing import List

from dip.pipeline.deliberation.reasoning.schema import AgentMessage, MessageType
from dip.pipeline.deliberation.reasoning.ministers.base_specialist import BaseSpecialist
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.telemetry.llm_tracer import tracer
from dip.core.Config.config import config
from dip.core.json_utils import strip_markdown_json


class EconomicSpecialist(BaseSpecialist):
    def __init__(self, message_bus: MessageBus):
        mandate = (
            "Focus: trade sanctions, energy supply, currency, debt leverage, FDI, supply chains, economic corridors. "
            "Answer: 'Are economic factors driving this behavior?'"
        )
        super().__init__("Economic", mandate, message_bus)

    async def process_message(self, message: AgentMessage):
        if message.message_type == MessageType.EVIDENCE_REQUEST and message.sender == "Orchestrator":
            # Phase 1: Formulate independent hypothesis based on evidence
            await self._formulate_hypothesis(message)
        elif message.message_type == MessageType.CHALLENGE and message.receiver == self.name:
            # Phase: Rebuttal
            await self._formulate_rebuttal(message)

    async def _formulate_hypothesis(self, trigger_msg: AgentMessage):
        prompt = f"""You are the Economic Agent for IND-Diplomat.
Mandate: {self.mandate}

Analyze the global evidence memory (if any) and formulate your hypothesis.
Use your analytical constraints to estimate the probability of ACTIVE_CONFLICT.

Respond in JSON:
{{
    "claim": "Your main hypothesis",
    "state": "ACTIVE_CONFLICT",
    "probability": 0.55,
    "confidence": 0.70,
    "reasoning_summary": "Explanation of your reasoning based on economic indicators."
}}"""
        try:
            response = await tracer.acompletion(
                layer="Layer4_Economic",
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
        except Exception as e:
            pass

    async def _formulate_rebuttal(self, challenge_msg: AgentMessage):
        prompt = f"""You are the Economic Agent.
You have been CHALLENGED by {challenge_msg.sender}.
Challenge Claim: {challenge_msg.claim}
Reasoning: {challenge_msg.reasoning_summary}

Formulate a REBUTTAL or REVISION to your previous belief.
Respond in JSON:
{{
    "claim": "Your rebuttal or revision",
    "state": "ACTIVE_CONFLICT",
    "probability": 0.50,
    "confidence": 0.65,
    "reasoning_summary": "Why you updated or held your belief."
}}"""
        try:
            response = await tracer.acompletion(
                layer="Layer4_Economic",
                model=config.LLM_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            data = json.loads(strip_markdown_json(response.choices[0].message.content))
            
            await self.update_belief(data.get("state", "UNKNOWN"), data.get("probability", 0.5))
            
            await self.send_message(
                receiver=challenge_msg.sender,
                message_type=MessageType.REBUTTAL,
                claim=data.get("claim", ""),
                round_num=challenge_msg.round + 1,
                state=data.get("state"),
                probability=data.get("probability"),
                confidence=data.get("confidence"),
                reasoning_summary=data.get("reasoning_summary", "")
            )
        except Exception as e:
            pass
