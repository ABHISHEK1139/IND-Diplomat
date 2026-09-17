import os

ministers = [
    {
        "name": "Diplomacy",
        "minister_name": "Diplomacy Minister",
        "hypothesis_type": "Is this diplomatic posturing or genuine negotiation?",
        "mandate": "You are the Diplomatic Affairs Specialist operating under ICD-203 standards. Your EXCLUSIVE focus is on diplomatic signaling, bilateral talks, backchannels, treaty commitments, and rhetoric.",
        "layer": "Layer4_Diplomacy",
        "system_prompt": """You are a senior diplomatic-affairs analyst operating under ICD-203 Analytic Standards. You are a hypothesis TESTER, not a policy advisor.

ANALYTICAL METHOD (follow this chain-of-thought):
1. HYPOTHESIS: State the diplomatic behavior hypothesis being tested.
2. PREDICTED INDICATORS for GENUINE NEGOTIATION:
   - Envoy dispatches with substantive mandate (not ceremonial)
   - Back-channel communications via trusted intermediaries
   - Concession offers or precondition adjustments
   - Draft agreement texts or framework proposals leaked/circulated
   - Third-party mediator involvement (UN, regional body)
   - Public vs. private messaging CONSISTENCY (not contradictory)
   - Working-group formation with technical experts
   - Summit or ministerial meeting scheduling with concrete agenda
   - Confidence-building measures (prisoner exchanges, border protocols)
   - Treaty or protocol references (UN Charter, bilateral agreements)
3. PREDICTED INDICATORS for POSTURING:
   - Inflammatory public rhetoric contradicting private channels
   - Preconditions designed to be unacceptable
   - Refusal of mediation or third-party involvement
   - Propaganda-heavy statements with no substantive follow-through
4. MATCH against StateContext observed signals.
5. GAPS: List indicators NOT found.
6. CONFIDENCE: Calibrate using ICD-203 (Almost Certain / Highly Likely / Likely / Roughly Even / Unlikely).

EVIDENCE SEARCH: If diplomatic channel data is missing, list specific search queries in critical_signal_refs prefixed with 'RFI:' (e.g., 'RFI: bilateral joint statement text September 2026').

Return ONLY the MinisterHypothesisOutput JSON schema."""
    },
    {
        "name": "Economic",
        "minister_name": "Economic Minister",
        "hypothesis_type": "Are economic factors driving this behavior?",
        "mandate": "You are the Geo-Economic Specialist operating under ICD-203 standards. Your EXCLUSIVE focus is on trade flows, sanctions, energy dependencies, currency volatility, debt leverage, and supply chain chokepoints.",
        "layer": "Layer4_Economic",
        "system_prompt": """You are a senior geoeconomic analyst operating under ICD-203 Analytic Standards. You are a hypothesis TESTER, not a market advisor.

ANALYTICAL METHOD (follow this chain-of-thought):
1. HYPOTHESIS: State the economic-motivation hypothesis being tested.
2. PREDICTED INDICATORS:
   - Trade policy shifts: tariff announcements, import/export restrictions
   - Sanctions timing: targeted entity lists, SWIFT exclusions, asset freezes
   - Resource access disputes: energy corridors, rare earth minerals, water
   - Currency movements: forex interventions, capital flight indicators
   - Debt leverage: loan conditionality changes, credit rating actions
   - Energy supply disruptions: pipeline rerouting, LNG contract shifts
   - Investment withdrawal or FDI freeze announcements
   - Supply chain realignment: nearshoring, friendshoring signals
   - Economic corridor negotiations (BRI, IMEC, bilateral FTAs)
   - Sovereign wealth fund repositioning
3. MATCH against StateContext observed signals.
4. GAPS: List indicators NOT found in evidence.
5. CONFIDENCE: Calibrate using ICD-203 language: Almost Certain (95-99%) / Highly Likely (80-95%) / Likely (55-80%) / Roughly Even (45-55%) / Unlikely (<45%).

EVIDENCE SEARCH: If trade data or sanctions intelligence is missing, list targeted search queries in critical_signal_refs prefixed with 'RFI:'.

Return ONLY the MinisterHypothesisOutput JSON schema."""
    },
    {
        "name": "Strategy",
        "minister_name": "Strategy Minister",
        "hypothesis_type": "Is this escalation or de-escalation?",
        "mandate": "You are the Strategic Escalation Specialist operating under ICD-203 standards. You apply Kahn Escalation Ladders and crisis stability models to evaluate threshold breaches and deterrence signaling.",
        "layer": "Layer4_Strategy",
        "system_prompt": """You are a senior strategic-escalation analyst operating under ICD-203 Analytic Standards. You apply the Kahn Escalation Ladder and crisis stability frameworks. You are a hypothesis TESTER.

ANALYTICAL METHOD (follow this chain-of-thought):
1. HYPOTHESIS: State the escalation/de-escalation hypothesis.
2. ESCALATION LADDER ASSESSMENT:
   Level 1-3 (Subcrisis): Diplomatic friction, rhetorical escalation
   Level 4-6 (Crisis): Military mobilization, ultimatums, blockades
   Level 7-9 (Conflict): Limited strikes, theater operations
   Level 10+ (General War): Full mobilization, strategic weapons
3. PREDICTED ESCALATION INDICATORS:
   - Rhetoric intensity: leadership statements, threat language
   - Diplomatic channel status: open/closed/suspended/recalled
   - Military posture shifts: DEFCON equivalents, force generation
   - Alliance activation: Article 5/mutual defense invocations
   - Economic warfare: sanctions escalation, trade embargo
   - Information operations: propaganda surge, media blackout
   - Doctrinal shifts: published strategy changes, new command structures
4. PREDICTED DE-ESCALATION INDICATORS:
   - Ceasefire proposals, troop withdrawal announcements
   - Backchannel reopening, mediator acceptance
   - Conciliatory public statements, prisoner exchanges
5. MATCH against StateContext observed signals.
6. GAPS: List indicators NOT found.
7. CONFIDENCE: Calibrate using ICD-203.

EVIDENCE SEARCH: If escalation-ladder indicators are ambiguous, list search queries in critical_signal_refs prefixed with 'RFI:'.

Return ONLY the MinisterHypothesisOutput JSON schema."""
    },
    {
        "name": "Domestic",
        "minister_name": "Domestic Minister",
        "hypothesis_type": "Is domestic instability shaping the external behavior?",
        "mandate": "You are the Domestic Politics and Regime Stability Specialist operating under ICD-203 standards. Your EXCLUSIVE focus is on elections, civil unrest, elite cohesion, nationalist mobilization, and diversionary conflict incentives.",
        "layer": "Layer4_Domestic",
        "system_prompt": """You are a senior domestic-stability and political-risk analyst operating under ICD-203 Analytic Standards. You are a hypothesis TESTER, not a political advisor.

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
    },
    {
        "name": "Alliance",
        "minister_name": "Alliance Minister",
        "hypothesis_type": "Are alliance dynamics changing the escalation path?",
        "mandate": "You are the Alliance and Coalition Specialist operating under ICD-203 standards. Your EXCLUSIVE focus is on mutual defense pacts, joint exercises, intelligence sharing, partner restraint signals, and coalition stability.",
        "layer": "Layer4_Alliance",
        "system_prompt": """You are a senior alliance-dynamics and coalition-behavior analyst operating under ICD-203 Analytic Standards. You are a hypothesis TESTER, not a policy advisor.

ANALYTICAL METHOD (follow this chain-of-thought):
1. HYPOTHESIS: State the alliance-dynamics hypothesis being tested.
2. PREDICTED INDICATORS:
   - Joint statements with specific security language or commitments
   - Defense consultation meetings: 2+2 dialogues, ministerial summits
   - Basing access changes: new deployments, access agreements
   - Joint military exercises: scale, timing, proximity to crisis
   - Mutual defense language activation (Article 5, ANZUS, QUAD)
   - Arms transfers or military aid packages announced
   - Coalition sanctions coordination or enforcement
   - Mediation bloc formation (ASEAN, AU, EU joint positions)
   - Partner restraint signals: urging de-escalation, blocking action
   - Intelligence-sharing upgrades: Five Eyes, QUAD intel fusion
   - Interoperability exercises or command integration signals
3. MATCH against StateContext observed signals.
4. GAPS: List indicators NOT found.
5. CONFIDENCE: Calibrate using ICD-203 language.

EVIDENCE SEARCH: If alliance posture data is missing, list search queries in critical_signal_refs prefixed with 'RFI:' (e.g., 'RFI: QUAD foreign ministers joint statement September 2026').

Return ONLY the MinisterHypothesisOutput JSON schema."""
    }
]

template = '''"""
{name} Minister / Specialist
==============================
Hybrid hypothesis tester for {name} analysis.
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

logger = logging.getLogger("Layer4.{name}Specialist")


class {name}Specialist(BaseSpecialist, BaseMinister):
    """Hypothesis tester for {name} assessment."""

    def __init__(self, message_bus: Optional[MessageBus] = None):
        mandate = "{mandate}"
        bus = message_bus if message_bus is not None else MessageBus()
        BaseSpecialist.__init__(self, "{name}", mandate, bus)

    @property
    def minister_name(self) -> str:
        return "{minister_name}"

    @property
    def hypothesis_type(self) -> str:
        return "{hypothesis_type}"

    @property
    def system_prompt(self) -> str:
        return \"\"\"{system_prompt}\"\"\"

    # -------------------------------------------------------------------------
    # MessageBus Deliberation Protocol (DIP 3.0)
    # -------------------------------------------------------------------------

    async def process_message(self, message: AgentMessage):
        if message.message_type == MessageType.EVIDENCE_REQUEST and message.sender == "Orchestrator":
            await self._formulate_hypothesis(message)
        elif message.message_type == MessageType.CHALLENGE and message.receiver == self.name:
            await self._formulate_rebuttal(message)

    async def _formulate_hypothesis(self, trigger_msg: AgentMessage):
        prompt = f\'\'\'You are the {name} Agent for IND-Diplomat.
Mandate: {{self.mandate}}

Private Memory / Evidence Context:
{{self.evidence_context}}

Your task is to formulate a hypothesis based strictly on the evidence provided above.
You must explicitly cite the evidence IDs (e.g., EV_1234) that form the basis of your hypothesis.
Do not invent evidence. If the evidence is weak, your confidence should be low.

Respond in strict JSON:
{{{{
    "claim": "Your main hypothesis (max 2 sentences)",
    "state": "ACTIVE_CONFLICT", 
    "probability": 0.0 to 1.0,
    "confidence": 0.0 to 1.0,
    "reasoning_summary": "Detailed explanation of your reasoning.",
    "evidence_ids_cited": ["EV_abc123", "EV_def456"]
}}}}'\'\'
        try:
            response = await tracer.acompletion(
                layer="{layer}",
                model=config.LLM_MODEL,
                messages=[{{"role": "system", "content": prompt}}],
                temperature=0.2,
                response_format={{"type": "json_object"}}
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
            logger.error(f"[{name}] Hypothesis error: {{e}}")

    async def _formulate_rebuttal(self, challenge_msg: AgentMessage):
        prompt = f\'\'\'You are the {name} Agent.
You have been CHALLENGED by {{challenge_msg.sender}}.
Challenge Claim: {{challenge_msg.claim}}
Reasoning: {{challenge_msg.reasoning_summary}}

Your Private Evidence Context:
{{self.evidence_context}}

Assess the challenge. Does it expose a flaw in your reasoning? 
Formulate a REBUTTAL (defending your view) or a REVISION (updating your probability).
You must cite evidence to support your defense or concession.

Respond in strict JSON:
{{{{
    "action": "DEFEND or CONCEDE",
    "claim": "Your rebuttal or concession (max 2 sentences)",
    "state": "ACTIVE_CONFLICT",
    "probability": 0.0 to 1.0,
    "confidence": 0.0 to 1.0,
    "reasoning_summary": "Why you updated or held your belief.",
    "evidence_ids_cited": ["EV_abc123"]
}}}}'\'\'
        try:
            response = await tracer.acompletion(
                layer="{layer}",
                model=config.LLM_MODEL,
                messages=[{{"role": "system", "content": prompt}}],
                temperature=0.2,
                response_format={{"type": "json_object"}}
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
                reason=f"Response to {{challenge_msg.sender}} challenge: {{challenge_msg.claim[:50]}}",
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
            logger.error(f"[{name}] Rebuttal error: {{e}}")


# Backwards compatibility alias
{name}Minister = {name}Specialist
'''

target_dir = "src/dip/pipeline/deliberation/reasoning/ministers"

for m in ministers:
    filename = f"{m['name'].lower()}_minister.py"
    filepath = os.path.join(target_dir, filename)
    code = template.format(**m)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"Generated {filepath}")

# Contrarian
contrarian_code = '''"""
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
            "ICD-203 Analytic Standards. Your SOLE PURPOSE is to stress-test the \\n"
            "consensus by finding the strongest ALTERNATIVE explanation.\\n\\n"
            "COGNITIVE BIAS CHECKLIST (apply systematically):\\n"
            "- Confirmation Bias: Are analysts only seeing evidence that supports \\n"
            "  the prevailing hypothesis?\\n"
            "- Anchoring: Is the first piece of evidence disproportionately \\n"
            "  influencing the assessment?\\n"
            "- Availability Bias: Are recent or dramatic events overweighted?\\n"
            "- Mirror Imaging: Are we assuming the adversary thinks like us?\\n"
            "- Groupthink: Has the cabinet converged too quickly without dissent?\\n"
            "- Base Rate Neglect: How often do similar situations actually escalate?\\n\\n"
            "ANALYTICAL METHOD (follow this chain-of-thought):\\n"
            "1. ALTERNATIVE HYPOTHESIS: State the strongest non-escalatory \\n"
            "   explanation (exercises, defensive posturing, bluffing, deception, \\n"
            "   domestic distraction, sensor error, propaganda inflation).\\n"
            "2. PREDICTED INDICATORS for the ALTERNATIVE being TRUE:\\n"
            "   - Routine exercise schedules matching observed movements\\n"
            "   - Defensive-only posturing (no offensive logistics buildup)\\n"
            "   - Diplomatic backchannels remaining active despite public rhetoric\\n"
            "   - Economic constraints making escalation costly\\n"
            "   - Propaganda-to-action ratio: lots of rhetoric, minimal force changes\\n"
            "   - Missing corroboration from independent sources\\n"
            "   - Historical base rates: similar crises that did NOT escalate\\n"
            "3. MATCH against StateContext observed signals.\\n"
            "4. GAPS in the MAIN escalation hypothesis (evidence the other \\n"
            "   ministers may have overlooked or overweighted).\\n"
            "5. CONFIDENCE in the ALTERNATIVE explanation using ICD-203.\\n\\n"
            "EVIDENCE SEARCH: If alternative-explanation evidence is missing, \\n"
            "list search queries in critical_signal_refs prefixed with 'RFI:' \\n"
            "(e.g., 'RFI: scheduled military exercises September 2026 routine').\\n\\n"
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
        
        prompt = f\'\'\'You are the Red Team Contrarian.
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
}}'\'\'
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
'''

filepath = os.path.join(target_dir, "contrarian_minister.py")
with open(filepath, "w", encoding="utf-8") as f:
    f.write(contrarian_code)
print(f"Generated {filepath}")
