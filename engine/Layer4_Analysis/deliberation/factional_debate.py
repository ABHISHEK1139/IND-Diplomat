"""
Factional Research Teams for explicit Escalation vs. De-escalation debate.
"""
from typing import List, Dict, Any
import logging
from dataclasses import dataclass

from engine.Layer4_Analysis.council_session import CouncilSession, FullContext
from engine.Layer4_Analysis.ministers.base_minister import MinisterReport
from engine.Layer4_Analysis.core.llm_client import llm_client

logger = logging.getLogger(__name__)

@dataclass
class DebateResult:
    escalation_arguments: str
    deescalation_arguments: str
    synthesis: str
    recommended_adjustment: str

class FactionalDebate:
    """
    Orchestrates an explicit debate between an Escalation faction and a De-escalation faction.
    """

    def __init__(self):
        pass

    def run_debate(
        self, 
        session: CouncilSession, 
        full_context: FullContext, 
        round1_reports: List[MinisterReport]
    ) -> DebateResult:
        """
        Runs the factional debate sequentially:
        1. Escalation faction reviews state and reports -> formulates arguments for escalation.
        2. De-escalation faction reviews state and reports -> formulates arguments for de-escalation.
        3. Moderator synthesizes both sides.
        """
        logger.info("[FACTIONAL-DEBATE] Starting explicit Escalation vs. De-escalation debate...")
        
        # Prepare context payload
        context_str = self._format_context(full_context, round1_reports)

        # 1. Escalation Faction
        escalation_args = self._generate_escalation_arguments(context_str)
        
        # 2. De-escalation Faction
        deescalation_args = self._generate_deescalation_arguments(context_str)

        # 3. Debate Moderator Synthesis
        synthesis, recommendation = self._synthesize_debate(escalation_args, deescalation_args, context_str)
        
        logger.info("[FACTIONAL-DEBATE] Debate concluded. Recommendation: %s", recommendation)

        return DebateResult(
            escalation_arguments=escalation_args,
            deescalation_arguments=deescalation_args,
            synthesis=synthesis,
            recommended_adjustment=recommendation
        )

    def _format_context(self, context: FullContext, reports: List[MinisterReport]) -> str:
        lines = []
        lines.append("=== STATE CONTEXT ===")
        lines.append(f"Escalation Score: {getattr(context, 'escalation_score', 0.0)}")
        lines.append(f"Pressures: {getattr(context, 'pressures', {})}")
        lines.append(f"Signal Confidence: {getattr(context, 'signal_confidence', {})}")
        lines.append("\n=== ROUND 1 FINDINGS ===")
        for r in reports:
            lines.append(f"Minister: {r.minister_name}")
            lines.append(f"Primary Drivers: {'; '.join(r.primary_drivers or [])}")
            lines.append(f"Risk Adjustment: {r.risk_level_adjustment}")
        return "\n".join(lines)

    def _generate_escalation_arguments(self, context_str: str) -> str:
        prompt = (
            "You represent the ESCALATION FACTION (Hawks) in a geopolitical risk assessment.\n"
            "Your goal is to identify and strongly argue why the current context and evidence point toward ESCALATION.\n"
            "Focus on worst-case scenarios, malicious intent, military mobilization, and structural pressures.\n\n"
            f"{context_str}\n\n"
            "Produce a concise, persuasive argument (max 3 paragraphs) for why the council should assess a higher threat level."
        )
        return llm_client.generate_sync(prompt, system_prompt="You are the Escalation Faction lead analyst.")

    def _generate_deescalation_arguments(self, context_str: str) -> str:
        prompt = (
            "You represent the DE-ESCALATION FACTION (Doves) in a geopolitical risk assessment.\n"
            "Your goal is to identify and strongly argue why the current context and evidence point toward DE-ESCALATION or STABILITY.\n"
            "Focus on diplomatic off-ramps, economic constraints, benign interpretations of military movement, and structural stabilizers.\n\n"
            f"{context_str}\n\n"
            "Produce a concise, persuasive argument (max 3 paragraphs) for why the council should maintain or lower the threat level."
        )
        return llm_client.generate_sync(prompt, system_prompt="You are the De-escalation Faction lead analyst.")

    def _synthesize_debate(self, esc_args: str, deesc_args: str, context_str: str) -> tuple[str, str]:
        prompt = (
            "You are the DEBATE MODERATOR for the geopolitical risk council.\n"
            "You have heard arguments from both the Escalation Faction and the De-escalation Faction.\n\n"
            "=== ESCALATION ARGUMENTS ===\n"
            f"{esc_args}\n\n"
            "=== DE-ESCALATION ARGUMENTS ===\n"
            f"{deesc_args}\n\n"
            "Based on these arguments and the underlying evidence, provide:\n"
            "1. A synthesized summary of the most credible points from both sides.\n"
            "2. A final 'recommended_adjustment' which must be one of: [increase, decrease, maintain].\n\n"
            "Output format:\n"
            "SYNTHESIS: <your 1-2 paragraph summary>\n"
            "RECOMMENDATION: <increase/decrease/maintain>"
        )
        result = llm_client.generate_sync(prompt, system_prompt="You are an objective geopolitical debate moderator.")
        
        # Parse result
        synthesis = result
        recommendation = "maintain"
        if "RECOMMENDATION: increase" in result.lower():
            recommendation = "increase"
        elif "RECOMMENDATION: decrease" in result.lower():
            recommendation = "decrease"
            
        return synthesis, recommendation
