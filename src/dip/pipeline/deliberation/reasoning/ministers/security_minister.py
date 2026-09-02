"""
Security Minister / Specialist
==============================
Hybrid hypothesis tester for genuine military threat assessment.
Supports:
  - Dual-mode deterministic rails & RFI search (DIP 2.0 BaseMinister)
  - Asynchronous pub/sub deliberation bus (DIP 3.0 BaseSpecialist)
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from dip.pipeline.deliberation.reasoning.schema import AgentMessage, MessageType
from dip.pipeline.deliberation.reasoning.ministers.base_specialist import BaseSpecialist
from dip.pipeline.deliberation.reasoning.ministers.base import BaseMinister
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.telemetry.llm_tracer import tracer
from dip.core.Config.config import config
from dip.core.json_utils import strip_markdown_json

logger = logging.getLogger("Layer4.SecuritySpecialist")


class SecuritySpecialist(BaseSpecialist, BaseMinister):
    """Hypothesis tester for genuine military threat assessment."""

    def __init__(self, message_bus: Optional[MessageBus] = None):
        mandate = (
            "You are the Military Security Specialist operating under ICD-203 standards. "
            "Your EXCLUSIVE focus is on military capability, mobilization, force posture, "
            "logistics, readiness, WMDs, and hard military signaling."
        )
        bus = message_bus if message_bus is not None else MessageBus()
        BaseSpecialist.__init__(self, "Security", mandate, bus)

    @property
    def minister_name(self) -> str:
        return "Security Minister"

    @property
    def hypothesis_type(self) -> str:
        return "Is this a genuine military threat?"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a senior military-intelligence analyst operating under "
            "ICD-203 Analytic Standards. You are a hypothesis TESTER, not a "
            "decision-maker.\n\n"
            "ANALYTICAL METHOD (follow this chain-of-thought):\n"
            "1. HYPOTHESIS: State the military threat hypothesis being tested.\n"
            "2. PREDICTED INDICATORS: List the specific, observable signals that \n"
            "   MUST be present if the hypothesis is TRUE. Think about:\n"
            "   - Forward troop deployments & mechanized brigade positioning\n"
            "   - Air defense radar battery activations & SAM redeployments\n"
            "   - Naval task force repositioning & carrier strike group movements\n"
            "   - Logistics surge: fuel depot activity, ammunition resupply convoys\n"
            "   - Communications intercepts: encrypted traffic spikes, EMCON shifts\n"
            "   - Runway extensions, hardened shelter construction, FOB activation\n"
            "   - Mobilization orders: reserve callups, leave cancellations\n"
            "   - SIGINT/ELINT anomalies indicating targeting or ISR activity\n"
            "3. MATCH: Compare predicted indicators against observed StateContext signals.\n"
            "4. GAPS: List predicted indicators NOT found in the evidence.\n"
            "5. CONFIDENCE: Calibrate using ICD-203 language:\n"
            "   - Almost Certain (95-99%): All critical indicators present\n"
            "   - Highly Likely (80-95%): Most indicators present, minor gaps\n"
            "   - Likely (55-80%): Majority present but notable gaps\n"
            "   - Roughly Even (45-55%): Evidence split or ambiguous\n"
            "   - Unlikely (<45%): Few indicators match, alternative explanation stronger\n\n"
            "EVIDENCE SEARCH: If critical indicators are missing and you believe \n"
            "additional web search could resolve them, list specific search queries \n"
            "in critical_signal_refs prefixed with 'RFI:' (e.g., 'RFI: satellite imagery \n"
            "LAC sector troop positions September 2026').\n\n"
            "Return ONLY the MinisterHypothesisOutput JSON schema."
        )

    # -------------------------------------------------------------------------
    # MessageBus Deliberation Protocol (DIP 3.0)
    # -------------------------------------------------------------------------

    async def process_message(self, message: AgentMessage):
        if message.message_type == MessageType.EVIDENCE_REQUEST and message.sender == "Orchestrator":
            await self._formulate_hypothesis(message)
        elif message.message_type == MessageType.CHALLENGE and message.receiver == self.name:
            await self._formulate_rebuttal(message)

    async def _formulate_hypothesis(self, trigger_msg: AgentMessage):
        prompt = f'''You are the Security Agent for IND-Diplomat.
Mandate: {self.mandate}

Private Memory / Evidence Context:
{self.evidence_context}

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
                layer="Layer4_Security",
                model=config.LLM_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            data = json.loads(strip_markdown_json(response.choices[0].message.content))
            
            # Defensive float typecasting
            raw_prob = data.get("probability", 0.5)
            try:
                prob = float(raw_prob) if raw_prob is not None else 0.5
            except (ValueError, TypeError):
                prob = 0.5
            prob = max(0.0, min(1.0, prob))

            raw_conf = data.get("confidence", 0.5)
            try:
                conf = float(raw_conf) if raw_conf is not None else 0.5
            except (ValueError, TypeError):
                conf = 0.5
            conf = max(0.0, min(1.0, conf))

            state = data.get("state", "UNKNOWN")
            evidence_cited = data.get("evidence_ids_cited", [])
            claim = data.get("claim", "")
            reasoning = data.get("reasoning_summary", "")

            # Phase 9: Record belief revision with reason
            await self.update_belief(
                state=state, 
                prob=prob,
                reason="Initial Hypothesis Formulation",
                evidence_ids=evidence_cited,
                round_num=trigger_msg.round
            )
            
            await self.send_message(
                receiver="BROADCAST",
                message_type=MessageType.HYPOTHESIS,
                claim=claim,
                round_num=trigger_msg.round,
                state=state,
                probability=prob,
                confidence=conf,
                evidence_ids=evidence_cited,
                reasoning_summary=reasoning
            )
        except Exception as e:
            logger.error(f"[Security] Hypothesis error: {e}")

    async def _formulate_rebuttal(self, challenge_msg: AgentMessage):
        prompt = f'''You are the Security Agent.
You have been CHALLENGED by {challenge_msg.sender}.
Challenge Claim: {challenge_msg.claim}
Reasoning: {challenge_msg.reasoning_summary}

Your Private Evidence Context:
{self.evidence_context}

Assess the challenge. Does it expose a flaw in your reasoning? 
Formulate a REBUTTAL (defending your view) or a REVISION (updating your probability).
You must cite evidence to support your defense or concession.

Respond in strict JSON:
{{
    "action": "DEFEND or CONCEDE",
    "claim": "Your rebuttal or concession (max 2 sentences)",
    "state": "ACTIVE_CONFLICT",
    "probability": 0.0 to 1.0,
    "confidence": 0.0 to 1.0,
    "reasoning_summary": "Why you updated or held your belief.",
    "evidence_ids_cited": ["EV_abc123"]
}}'''
        try:
            response = await tracer.acompletion(
                layer="Layer4_Security",
                model=config.LLM_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            data = json.loads(strip_markdown_json(response.choices[0].message.content))
            
            # Defensive float typecasting
            raw_prob = data.get("probability", 0.5)
            try:
                prob = float(raw_prob) if raw_prob is not None else 0.5
            except (ValueError, TypeError):
                prob = 0.5
            prob = max(0.0, min(1.0, prob))

            raw_conf = data.get("confidence", 0.5)
            try:
                conf = float(raw_conf) if raw_conf is not None else 0.5
            except (ValueError, TypeError):
                conf = 0.5
            conf = max(0.0, min(1.0, conf))

            state = data.get("state", "UNKNOWN")
            evidence_cited = data.get("evidence_ids_cited", [])
            claim = data.get("claim", "")
            reasoning = data.get("reasoning_summary", "")
            action = str(data.get("action", "DEFEND")).upper()

            msg_type = MessageType.REVISION if "CONCEDE" in action else MessageType.REBUTTAL
            
            # Phase 9: Record belief revision with reason
            await self.update_belief(
                state=state, 
                prob=prob,
                reason=f"Response to {challenge_msg.sender} challenge: {challenge_msg.claim[:50]}",
                evidence_ids=evidence_cited,
                round_num=challenge_msg.round
            )
            
            await self.send_message(
                receiver=challenge_msg.sender,
                message_type=msg_type,
                claim=claim,
                round_num=challenge_msg.round,
                state=state,
                probability=prob,
                confidence=conf,
                evidence_ids=evidence_cited,
                reasoning_summary=reasoning
            )
        except Exception as e:
            logger.error(f"[Security] Rebuttal error: {e}")


# Backwards compatibility alias
SecurityMinister = SecuritySpecialist
