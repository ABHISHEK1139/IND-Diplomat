"""
Domestic Minister / Specialist
==============================
Hybrid hypothesis tester for Domestic analysis.
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

logger = logging.getLogger("Layer4.DomesticSpecialist")


class DomesticSpecialist(BaseSpecialist, BaseMinister):
    """Hypothesis tester for Domestic assessment."""

    def __init__(self, message_bus: Optional[MessageBus] = None):
        mandate = "You are the Domestic Politics and Regime Stability Specialist operating under ICD-203 standards. Your EXCLUSIVE focus is on elections, civil unrest, elite cohesion, nationalist mobilization, and diversionary conflict incentives."
        bus = message_bus if message_bus is not None else MessageBus()
        BaseSpecialist.__init__(self, "Domestic", mandate, bus)

    @property
    def minister_name(self) -> str:
        return "Domestic Minister"

    @property
    def hypothesis_type(self) -> str:
        return "Is domestic instability shaping the external behavior?"

    @property
    def system_prompt(self) -> str:
        return """You are a senior domestic-stability and political-risk analyst operating under ICD-203 Analytic Standards. You are a hypothesis TESTER, not a political advisor.

ANALYTICAL METHOD (follow this chain-of-thought):
1. HYPOTHESIS: State the domestic-instability hypothesis being tested.
2. PREDICTED INDICATORS:
   - Mass protests or civil unrest: scale, frequency, geographic spread
   - Elite fragmentation: factional splits, purges, defections
   - Emergency powers invocation: martial law, curfews, media blackouts
   - Diversionary conflict incentives: 'rally around the flag' dynamics
   - Economic pain indicators: inflation spikes, unemployment surges
   - Leadership vulnerability: approval ratings, succession uncertainty
   - Nationalist mobilization: state-sponsored rallies, propaganda surge
   - Internal security deployments: police/paramilitary mobilization
   - Legislative or judicial challenges to executive authority
   - Social media sentiment shifts: hashtag campaigns, information ops
3. MATCH against StateContext observed signals.
4. GAPS: List indicators NOT found.
5. CONFIDENCE: Calibrate using ICD-203 language: Almost Certain / Highly Likely / Likely / Roughly Even / Unlikely.

EVIDENCE SEARCH: If domestic political intelligence is missing, list search queries in critical_signal_refs prefixed with 'RFI:' (e.g., 'RFI: protest activity capital city September 2026').

Return ONLY the MinisterHypothesisOutput JSON schema."""

    # -------------------------------------------------------------------------
    # MessageBus Deliberation Protocol (DIP 3.0)
    # -------------------------------------------------------------------------

    async def process_message(self, message: AgentMessage):
        if message.message_type == MessageType.EVIDENCE_REQUEST and message.sender == "Orchestrator":
            await self._formulate_hypothesis(message)
        elif message.message_type == MessageType.CHALLENGE and message.receiver == self.name:
            await self._formulate_rebuttal(message)

    async def _formulate_hypothesis(self, trigger_msg: AgentMessage):
        prompt = f'''You are the Domestic Agent for IND-Diplomat.
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
                layer="Layer4_Domestic",
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
            logger.error(f"[Domestic] Hypothesis error: {e}")

    async def _formulate_rebuttal(self, challenge_msg: AgentMessage):
        prompt = f'''You are the Domestic Agent.
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
                layer="Layer4_Domestic",
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
            logger.error(f"[Domestic] Rebuttal error: {e}")


# Backwards compatibility alias
DomesticMinister = DomesticSpecialist
