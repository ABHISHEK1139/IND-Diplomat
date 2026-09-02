import json
import logging
from typing import List

from dip.pipeline.deliberation.reasoning.schema import AgentMessage, MessageType
from dip.pipeline.deliberation.reasoning.ministers.base_specialist import BaseSpecialist
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.telemetry.llm_tracer import tracer
from dip.core.Config.config import config
from dip.core.json_utils import strip_markdown_json

logger = logging.getLogger("Layer4.AllianceSpecialist")

class AllianceSpecialist(BaseSpecialist):
    def __init__(self, message_bus: MessageBus):
        mandate = "You are the Alliance Specialist. Your EXCLUSIVE focus is on external commitments, joint military exercises, basing agreements, defense pacts, and proxy relationships. Analyze how third-party actors might be drawn into a conflict."
        super().__init__("Alliance", mandate, message_bus)

    async def process_message(self, message: AgentMessage):
        if message.message_type == MessageType.EVIDENCE_REQUEST and message.sender == "Orchestrator":
            await self._formulate_hypothesis(message)
        elif message.message_type == MessageType.CHALLENGE and message.receiver == self.name:
            await self._formulate_rebuttal(message)

    async def _formulate_hypothesis(self, trigger_msg: AgentMessage):
        prompt = f'''You are the Alliance Agent for IND-Diplomat.
Mandate: {self.mandate}

Private Memory / Evidence Context:
{self.evidence_context}

Your task is to formulate a hypothesis based strictly on the evidence provided above.
You must explicitly cite the evidence IDs (e.g., EV_1234) that form the basis of your hypothesis.
Do not invent evidence. If the evidence is weak, your confidence should be low.

Respond in strict JSON:
{
    "claim": "Your main hypothesis (max 2 sentences)",
    "state": "ACTIVE_CONFLICT", 
    "probability": 0.0 to 1.0,
    "confidence": 0.0 to 1.0,
    "reasoning_summary": "Detailed explanation of your reasoning.",
    "evidence_ids_cited": ["EV_abc123", "EV_def456"]
}'''
        try:
            response = await tracer.acompletion(
                layer="Layer4_Alliance",
                model=config.LLM_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            data = json.loads(strip_markdown_json(response.choices[0].message.content))
            
            # Phase 9: Record belief revision with reason
            await self.update_belief(
                state=data.get("state", "UNKNOWN"), 
                prob=data.get("probability", 0.5),
                reason="Initial Hypothesis Formulation",
                evidence_ids=data.get("evidence_ids_cited", []),
                round_num=trigger_msg.round
            )
            
            await self.send_message(
                receiver="BROADCAST",
                message_type=MessageType.HYPOTHESIS,
                claim=data.get("claim", ""),
                round_num=trigger_msg.round,
                state=data.get("state"),
                probability=data.get("probability"),
                confidence=data.get("confidence"),
                evidence_ids=data.get("evidence_ids_cited", []),
                reasoning_summary=data.get("reasoning_summary", "")
            )
        except Exception as e:
            logger.error(f"[Alliance] Hypothesis error: {e}")

    async def _formulate_rebuttal(self, challenge_msg: AgentMessage):
        prompt = f'''You are the Alliance Agent.
You have been CHALLENGED by {challenge_msg.sender}.
Challenge Claim: {challenge_msg.claim}
Reasoning: {challenge_msg.reasoning_summary}

Your Private Evidence Context:
{self.evidence_context}

Assess the challenge. Does it expose a flaw in your reasoning? 
Formulate a REBUTTAL (defending your view) or a REVISION (updating your probability).
You must cite evidence to support your defense or concession.

Respond in strict JSON:
{
    "claim": "Your rebuttal or concession (max 2 sentences)",
    "state": "ACTIVE_CONFLICT",
    "probability": 0.0 to 1.0,
    "confidence": 0.0 to 1.0,
    "reasoning_summary": "Why you updated or held your belief.",
    "evidence_ids_cited": ["EV_abc123"]
}'''
        try:
            response = await tracer.acompletion(
                layer="Layer4_Alliance",
                model=config.LLM_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            data = json.loads(strip_markdown_json(response.choices[0].message.content))
            
            # Phase 9: Record belief revision with reason (e.g., conceded to challenge)
            await self.update_belief(
                state=data.get("state", "UNKNOWN"), 
                prob=data.get("probability", 0.5),
                reason=f"Revised in response to {challenge_msg.sender} challenge: {challenge_msg.claim[:50]}",
                evidence_ids=data.get("evidence_ids_cited", []),
                round_num=challenge_msg.round
            )
            
            await self.send_message(
                receiver=challenge_msg.sender,
                message_type=MessageType.REBUTTAL,
                claim=data.get("claim", ""),
                round_num=challenge_msg.round + 1,
                state=data.get("state"),
                probability=data.get("probability"),
                confidence=data.get("confidence"),
                evidence_ids=data.get("evidence_ids_cited", []),
                reasoning_summary=data.get("reasoning_summary", "")
            )
        except Exception as e:
            logger.error(f"[Alliance] Rebuttal error: {e}")
