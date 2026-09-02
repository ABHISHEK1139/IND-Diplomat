"""
Contrarian Minister / Specialist
================================
Hybrid Red Team devil's advocate tester.
Supports:
  - Dual-mode deterministic rails & RFI search (DIP 2.0 BaseMinister)
  - Asynchronous pub/sub deliberation bus (DIP 3.0 BaseSpecialist)
"""

from __future__ import annotations

import json
import logging
import random
from typing import List, Optional

from dip.pipeline.deliberation.reasoning.schema import AgentMessage, MessageType
from dip.pipeline.deliberation.reasoning.ministers.base_specialist import BaseSpecialist
from dip.pipeline.deliberation.reasoning.ministers.base import BaseMinister
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.telemetry.llm_tracer import tracer
from dip.core.Config.config import config
from dip.core.json_utils import strip_markdown_json

logger = logging.getLogger("Layer4.ContrarianSpecialist")


class ContrarianSpecialist(BaseSpecialist, BaseMinister):
    """Hypothesis tester for deception, false positives, and de-escalation."""

    def __init__(self, message_bus: Optional[MessageBus] = None):
        mandate = (
            "You are the Red Team Contrarian operating under ICD-203 standards. "
            "Your SOLE PURPOSE is to stress-test the consensus by finding the strongest "
            "ALTERNATIVE explanation (exercises, bluffing, posturing, deception)."
        )
        bus = message_bus if message_bus is not None else MessageBus()
        BaseSpecialist.__init__(self, "Contrarian", mandate, bus)
        self.hypotheses_seen: List[AgentMessage] = []

    @property
    def minister_name(self) -> str:
        return "Contrarian Minister"

    @property
    def hypothesis_type(self) -> str:
        return "What is the strongest non-escalatory or deceptive explanation?"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a senior Red Team / Devil's Advocate analyst operating under "
            "ICD-203 Analytic Standards. Your SOLE PURPOSE is to stress-test the \n"
            "consensus by finding the strongest ALTERNATIVE explanation.\n\n"
            "COGNITIVE BIAS CHECKLIST (apply systematically):\n"
            "- Confirmation Bias: Are analysts only seeing evidence that supports \n"
            "  the prevailing hypothesis?\n"
            "- Anchoring: Is the first piece of evidence disproportionately \n"
            "  influencing the assessment?\n"
            "- Availability Bias: Are recent or dramatic events overweighted?\n"
            "- Mirror Imaging: Are we assuming the adversary thinks like us?\n"
            "- Groupthink: Has the cabinet converged too quickly without dissent?\n"
            "- Base Rate Neglect: How often do similar situations actually escalate?\n\n"
            "ANALYTICAL METHOD (follow this chain-of-thought):\n"
            "1. ALTERNATIVE HYPOTHESIS: State the strongest non-escalatory \n"
            "   explanation (exercises, defensive posturing, bluffing, deception, \n"
            "   domestic distraction, sensor error, propaganda inflation).\n"
            "2. PREDICTED INDICATORS for the ALTERNATIVE being TRUE:\n"
            "   - Routine exercise schedules matching observed movements\n"
            "   - Defensive-only posturing (no offensive logistics buildup)\n"
            "   - Diplomatic backchannels remaining active despite public rhetoric\n"
            "   - Economic constraints making escalation costly\n"
            "   - Propaganda-to-action ratio: lots of rhetoric, minimal force changes\n"
            "   - Missing corroboration from independent sources\n"
            "   - Historical base rates: similar crises that did NOT escalate\n"
            "3. MATCH against StateContext observed signals.\n"
            "4. GAPS in the MAIN escalation hypothesis (evidence the other \n"
            "   ministers may have overlooked or overweighted).\n"
            "5. CONFIDENCE in the ALTERNATIVE explanation using ICD-203.\n\n"
            "EVIDENCE SEARCH: If alternative-explanation evidence is missing, \n"
            "list search queries in critical_signal_refs prefixed with 'RFI:' \n"
            "(e.g., 'RFI: scheduled military exercises September 2026 routine').\n\n"
            "Return ONLY the MinisterHypothesisOutput JSON schema."
        )

    # -------------------------------------------------------------------------
    # MessageBus Deliberation Protocol (DIP 3.0)
    # -------------------------------------------------------------------------

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


# Backwards compatibility alias
ContrarianMinister = ContrarianSpecialist
