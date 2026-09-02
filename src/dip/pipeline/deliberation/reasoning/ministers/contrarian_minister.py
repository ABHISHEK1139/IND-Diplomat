import json
import logging
from typing import List
import random

from dip.pipeline.deliberation.reasoning.schema import AgentMessage, MessageType
from dip.pipeline.deliberation.reasoning.ministers.base_specialist import BaseSpecialist
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.telemetry.llm_tracer import tracer
from dip.core.Config.config import config
from dip.core.json_utils import strip_markdown_json

logger = logging.getLogger("Layer4.ContrarianSpecialist")

class ContrarianSpecialist(BaseSpecialist):
    def __init__(self, message_bus: MessageBus):
        mandate = "You are the Red Team Contrarian. Your EXCLUSIVE focus is adversarial attack. You do not generate independent hypotheses; you find the weakest link in others' reasoning."
        super().__init__("Contrarian", mandate, message_bus)
        self.hypotheses_seen: List[AgentMessage] = []

    async def process_message(self, message: AgentMessage):
        if message.message_type == MessageType.HYPOTHESIS and message.sender != self.name:
            self.hypotheses_seen.append(message)

        if message.message_type == MessageType.EVIDENCE_REQUEST and "Contrarian challenge" in message.claim:
            await self._execute_red_team_attack(message)

    def _select_attack_vector(self, target: AgentMessage) -> str:
        # Phase 7: Intelligent attack selection based on weakness
        if target.confidence is not None and target.confidence > 0.85:
            return "Base-rate attack: Challenge the high confidence by citing historical base rates."
        if not target.evidence_ids:
            return "Evidence attack: Challenge the lack of hard evidence cited."
        if target.probability is not None and target.probability < 0.2:
            return "Alternative-hypothesis attack: Challenge low probability by presenting a Black Swan alternative."
        
        vectors = [
            "Causal attack: Argue that correlation is being treated as causation.",
            "Temporal attack: Argue that recent events are dominating history disproportionately.",
            "Data-quality attack: Attack the reliability of the sources cited."
        ]
        return random.choice(vectors)

    async def _execute_red_team_attack(self, trigger_msg: AgentMessage):
        if not self.hypotheses_seen:
            return
            
        # Target the highest probability hypothesis
        target = max(self.hypotheses_seen, key=lambda x: getattr(x, 'probability', 0) or 0)
        attack_vector = self._select_attack_vector(target)
        
        prompt = f'''You are the Red Team Contrarian.
Your target is {target.sender}.
Target Claim: {target.claim}
Target Reasoning: {target.reasoning_summary}
Target Confidence: {target.confidence}

Attack Vector Assigned: {attack_vector}

Formulate a devastating, evidence-based challenge.
Respond in strict JSON:
{{
    "claim": "Your challenge statement",
    "reasoning_summary": "Detailed attack logic.",
    "counter_evidence": ["EV_counter1"]
}}'''
        try:
            response = await tracer.acompletion(
                layer="Layer4_Contrarian",
                model=config.LLM_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.4,
                response_format={"type": "json_object"}
            )
            data = json.loads(strip_markdown_json(response.choices[0].message.content))
            
            await self.send_message(
                receiver=target.sender,
                message_type=MessageType.CHALLENGE,
                claim=data.get("claim", ""),
                round_num=trigger_msg.round,
                counter_evidence=data.get("counter_evidence", []),
                reasoning_summary=data.get("reasoning_summary", "")
            )
        except Exception as e:
            logger.error(f"[Contrarian] Challenge error: {e}")
