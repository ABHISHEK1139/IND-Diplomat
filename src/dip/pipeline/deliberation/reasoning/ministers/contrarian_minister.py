import json
import random
from typing import List

from dip.pipeline.deliberation.reasoning.schema import AgentMessage, MessageType
from dip.pipeline.deliberation.reasoning.ministers.base_specialist import BaseSpecialist
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.telemetry.llm_tracer import tracer
from dip.core.Config.config import config
from dip.core.json_utils import strip_markdown_json

class ContrarianSpecialist(BaseSpecialist):
    def __init__(self, message_bus: MessageBus):
        mandate = (
            "ATTACK THE CURRENT HYPOTHESIS. Execute 6-dimension Red Team attacks: "
            "1. Evidence attack, 2. Causal attack, 3. Base-rate attack, 4. Data-quality attack, "
            "5. Temporal attack, 6. Alternative-hypothesis attack."
        )
        super().__init__("Contrarian", mandate, message_bus)
        
        # Track hypotheses to attack
        self.hypotheses_to_attack: List[AgentMessage] = []

    async def process_message(self, message: AgentMessage):
        if message.message_type == MessageType.HYPOTHESIS and message.sender != self.name:
            self.hypotheses_to_attack.append(message)
            
        elif message.message_type == MessageType.EVIDENCE_REQUEST and message.sender == "Orchestrator":
            # The orchestrator triggered a contrarian challenge phase
            if "Contrarian challenge" in message.claim:
                await self._execute_red_team_attack(message.round)

    async def _execute_red_team_attack(self, round_num: int):
        if not self.hypotheses_to_attack:
            return
            
        # Target the highest probability hypothesis
        target = max(self.hypotheses_to_attack, key=lambda x: x.probability if x.probability else 0)
        
        attack_types = [
            "Evidence attack: Are we counting the same event multiple times?",
            "Causal attack: Could this pattern have a non-escalatory explanation?",
            "Base-rate attack: How often does this happen normally without conflict?",
            "Data-quality attack: Is the source reliable?",
            "Temporal attack: Has this activity declined recently?",
            "Alternative-hypothesis attack: Is this deterrence signaling?"
        ]
        chosen_attack = random.choice(attack_types)
        
        prompt = f"""You are the Contrarian (Red Team) Agent for IND-Diplomat.
Mandate: {self.mandate}

Target Claim: {target.claim} by {target.sender}
Target Probability: {target.probability}
Target Reasoning: {target.reasoning_summary}

Execute the following attack type: {chosen_attack}

Respond in JSON:
{{
    "claim": "Your challenge statement",
    "reasoning_summary": "Explanation of the attack and why their probability is unjustified.",
    "severity": "HIGH|MEDIUM|LOW"
}}"""
        try:
            response = await tracer.acompletion(
                layer="Layer4_Contrarian",
                model=config.LLM_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            data = json.loads(strip_markdown_json(response.choices[0].message.content))
            
            await self.send_message(
                receiver=target.sender,
                message_type=MessageType.CHALLENGE,
                claim=f"[{chosen_attack.split(':')[0]}] {data.get('claim')}",
                round_num=round_num,
                reasoning_summary=data.get("reasoning_summary", "")
            )
        except Exception as e:
            pass
