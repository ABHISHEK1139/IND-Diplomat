import os

template = """import json
import logging
from typing import List

from dip.pipeline.deliberation.reasoning.schema import AgentMessage, MessageType
from dip.pipeline.deliberation.reasoning.ministers.base_specialist import BaseSpecialist
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.telemetry.llm_tracer import tracer
from dip.core.Config.config import config
from dip.core.json_utils import strip_markdown_json

logger = logging.getLogger("Layer4.{name}Specialist")

class {name}Specialist(BaseSpecialist):
    def __init__(self, message_bus: MessageBus):
        mandate = "{mandate}"
        super().__init__("{name}", mandate, message_bus)

    async def process_message(self, message: AgentMessage):
        if message.message_type == MessageType.EVIDENCE_REQUEST and message.sender == "Orchestrator":
            await self._formulate_hypothesis(message)
        elif message.message_type == MessageType.CHALLENGE and message.receiver == self.name:
            await self._formulate_rebuttal(message)

    async def _formulate_hypothesis(self, trigger_msg: AgentMessage):
        prompt = f'''You are the {name} Agent for IND-Diplomat.
Mandate: {{self.mandate}}

Private Memory / Evidence Context:
{{self.evidence_context}}

Your task is to formulate a hypothesis based strictly on the evidence provided above.
You must explicitly cite the evidence IDs (e.g., EV_1234) that form the basis of your hypothesis.
Do not invent evidence. If the evidence is weak, your confidence should be low.

Respond in strict JSON:
{{
    "claim": "Your main hypothesis (max 2 sentences)",
    "state": "ACTIVE_CONFLICT", 
    "probability": 0.0 to 1.0,
    "confidence": 0.0 to 1.0,
    "reasoning_summary": "Detailed explanation of your reasoning.",
    "evidence_ids_cited": ["EV_abc123", "EV_def456"]
}}'''
        try:
            response = await tracer.acompletion(
                layer="Layer4_{name}",
                model=config.LLM_MODEL,
                messages=[{{"role": "system", "content": prompt}}],
                temperature=0.2,
                response_format={{"type": "json_object"}}
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
            logger.error(f"[{name}] Hypothesis error: {{e}}")

    async def _formulate_rebuttal(self, challenge_msg: AgentMessage):
        prompt = f'''You are the {name} Agent.
You have been CHALLENGED by {{challenge_msg.sender}}.
Challenge Claim: {{challenge_msg.claim}}
Reasoning: {{challenge_msg.reasoning_summary}}

Your Private Evidence Context:
{{self.evidence_context}}

Assess the challenge. Does it expose a flaw in your reasoning? 
Formulate a REBUTTAL (defending your view) or a REVISION (updating your probability).
You must cite evidence to support your defense or concession.

Respond in strict JSON:
{{
    "claim": "Your rebuttal or concession (max 2 sentences)",
    "state": "ACTIVE_CONFLICT",
    "probability": 0.0 to 1.0,
    "confidence": 0.0 to 1.0,
    "reasoning_summary": "Why you updated or held your belief.",
    "evidence_ids_cited": ["EV_abc123"]
}}'''
        try:
            response = await tracer.acompletion(
                layer="Layer4_{name}",
                model=config.LLM_MODEL,
                messages=[{{"role": "system", "content": prompt}}],
                temperature=0.2,
                response_format={{"type": "json_object"}}
            )
            data = json.loads(strip_markdown_json(response.choices[0].message.content))
            
            # Phase 9: Record belief revision with reason (e.g., conceded to challenge)
            await self.update_belief(
                state=data.get("state", "UNKNOWN"), 
                prob=data.get("probability", 0.5),
                reason=f"Revised in response to {{challenge_msg.sender}} challenge: {{challenge_msg.claim[:50]}}",
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
            logger.error(f"[{name}] Rebuttal error: {{e}}")
"""

agents = {
    "security": {
        "name": "Security",
        "mandate": "You are the Military Security Specialist. Your EXCLUSIVE focus is on military capability, mobilization, force posture, logistics, readiness, WMDs, and hard military signaling. Ignore trade or diplomacy unless it directly impacts military readiness."
    },
    "diplomacy": {
        "name": "Diplomacy",
        "mandate": "You are the Diplomatic Specialist. Your EXCLUSIVE focus is on negotiations, treaties, backchannels, diplomatic signaling, embassies, UN resolutions, and rhetoric. Ignore troop movements unless they are used specifically as a diplomatic lever."
    },
    "economic": {
        "name": "Economic",
        "mandate": "You are the Economic Specialist. Your EXCLUSIVE focus is on sanctions, trade flows, energy pipelines, currency fluctuations, FDI, and supply chains. Ignore military posturing unless it disrupts trade."
    },
    "domestic": {
        "name": "Domestic",
        "mandate": "You are the Domestic Specialist. Your EXCLUSIVE focus is on internal regime stability, elections, protests, civil unrest, media censorship, and nationalist sentiment within the target state. Ignore external relations."
    },
    "alliance": {
        "name": "Alliance",
        "mandate": "You are the Alliance Specialist. Your EXCLUSIVE focus is on external commitments, joint military exercises, basing agreements, defense pacts, and proxy relationships. Analyze how third-party actors might be drawn into a conflict."
    },
    "strategy": {
        "name": "Strategy",
        "mandate": "You are the Strategy Specialist. Your EXCLUSIVE focus is on the escalation ladder, deterrence theory, red lines, and off-ramps. Synthesize how military, economic, and diplomatic moves combine to signal grand strategic intent."
    }
}

target_dir = "src/dip/pipeline/deliberation/reasoning/ministers"

for filename_prefix, config in agents.items():
    code = template.format(name=config["name"], mandate=config["mandate"])
    filepath = os.path.join(target_dir, f"{filename_prefix}_minister.py")
    with open(filepath, "w") as f:
        f.write(code)
    print(f"Written {filepath}")

# Contrarian is special, it needs 6-dimension attack logic.
contrarian_code = """import json
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
"""

filepath = os.path.join(target_dir, "contrarian_minister.py")
with open(filepath, "w") as f:
    f.write(contrarian_code)
print(f"Written {filepath}")
