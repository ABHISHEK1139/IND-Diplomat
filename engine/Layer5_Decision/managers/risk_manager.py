import json
import logging
from typing import Dict, Any
from engine.Layer4_Analysis.core.llm_client import llm_client

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Acts like the 'Risk Management Team' in TradingAgents.
    Evaluates the proposed policy responses for blowback, unintended escalation, or miscalculation risks.
    """
    def __init__(self):
        self.name = "Risk Manager"

    async def evaluate_risk(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("[%s] Evaluating risks of proposed strategy...", self.name)
        
        prompt = (
            "You are the Lead Risk Manager for a geopolitical command center.\n"
            "The Strategy Designer has proposed the following response options.\n"
            "Evaluate the blowback, unintended escalation, and collateral damage risks for the recommended option.\n\n"
            "=== PROPOSED STRATEGY ===\n"
            f"{json.dumps(strategy, indent=2)}\n\n"
            "Respond in valid JSON format ONLY with the following keys:\n"
            '- "blowback_risk": String describing the primary risk of the recommended action.\n'
            '- "risk_level": Float between 0.0 (safe) and 1.0 (highly dangerous).\n'
            '- "mitigation_steps": List of strings detailing how to minimize these risks.\n'
            '- "veto_recommendation": Boolean (true if the risk is so high the action should be vetoed/scaled back, false otherwise).'
        )

        try:
            response = await llm_client.generate(prompt, system_prompt="You are a risk management analyst.", json_mode=True)
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except Exception as e:
            logger.error("[%s] Failed to evaluate risk: %s", self.name, e)
            return {
                "blowback_risk": "Error during risk evaluation.",
                "risk_level": 1.0,
                "mitigation_steps": [],
                "veto_recommendation": True
            }
