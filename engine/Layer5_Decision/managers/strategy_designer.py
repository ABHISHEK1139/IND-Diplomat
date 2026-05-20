import json
import logging
from typing import Dict, Any
from engine.Layer4_Analysis.core.llm_client import llm_client
from engine.Layer4_Analysis.council_session import CouncilSession

logger = logging.getLogger(__name__)

class StrategyDesigner:
    """
    Acts like the 'Trader' in TradingAgents.
    Takes the final Council escalation assessment and formulates concrete diplomatic/military response options.
    """
    def __init__(self):
        self.name = "Strategy Designer"

    async def design_strategy(self, session: CouncilSession) -> Dict[str, Any]:
        logger.info("[%s] Designing response strategy based on council assessment...", self.name)
        
        prompt = (
            "You are the Lead Strategy Designer for a geopolitical risk command center.\n"
            "The Analysis Council has completed its deliberation and reached a final threat assessment.\n"
            "Your job is to formulate three concrete policy response options: Minimum, Moderate, and Maximum.\n\n"
            "=== COUNCIL SYNTHESIS ===\n"
            f"{session.synthesis_summary}\n\n"
            "=== FACTIONAL DEBATE ===\n"
            f"{getattr(session, 'factional_debate_result', 'N/A')}\n\n"
            "Respond in valid JSON format ONLY with the following keys:\n"
            '- "minimum_response": String detailing the most conservative action (e.g., diplomatic demarche).\n'
            '- "moderate_response": String detailing a balanced action (e.g., sanctions, defensive posturing).\n'
            '- "maximum_response": String detailing an aggressive action (e.g., mobilization, cyber retaliation).\n'
            '- "recommended_option": String specifying which option you recommend ("minimum", "moderate", or "maximum").\n'
            '- "rationale": String explaining why you chose this recommendation.'
        )

        try:
            response = await llm_client.generate(prompt, system_prompt="You are a strategic policy advisor.", json_mode=True)
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except Exception as e:
            logger.error("[%s] Failed to design strategy: %s", self.name, e)
            return {
                "minimum_response": "N/A",
                "moderate_response": "N/A",
                "maximum_response": "N/A",
                "recommended_option": "minimum",
                "rationale": "Error during strategy design."
            }
