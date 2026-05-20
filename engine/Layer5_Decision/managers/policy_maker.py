import json
import logging
from typing import Dict, Any
from engine.Layer4_Analysis.core.llm_client import llm_client

logger = logging.getLogger(__name__)

class PolicyMaker:
    """
    Acts like the 'Portfolio Manager' in TradingAgents.
    The final authoritative agent that reviews the Strategy and the Risk Management assessment
    to approve, reject, or modify the final policy actions.
    """
    def __init__(self):
        self.name = "Policy Maker"

    async def finalize_policy(self, strategy: Dict[str, Any], risk_assessment: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("[%s] Finalizing policy decision...", self.name)
        
        prompt = (
            "You are the Ultimate Policy Maker (equivalent to a Head of State or Portfolio Manager).\n"
            "You must make the final decision based on the Strategy Designer's proposals and the Risk Manager's warnings.\n\n"
            "=== STRATEGY PROPOSAL ===\n"
            f"{json.dumps(strategy, indent=2)}\n\n"
            "=== RISK ASSESSMENT ===\n"
            f"{json.dumps(risk_assessment, indent=2)}\n\n"
            "Determine the final action to take. You can approve the recommendation, select a different option, or modify it based on the risk warnings.\n"
            "Respond in valid JSON format ONLY with the following keys:\n"
            '- "final_decision": A clear string declaring the chosen action.\n'
            '- "justification": A string explaining why this balances the threat and the risk.\n'
            '- "execution_orders": List of strings detailing immediate next steps to execute the decision.'
        )

        try:
            response = await llm_client.generate(prompt, system_prompt="You are the ultimate policy decision maker.", json_mode=True)
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except Exception as e:
            logger.error("[%s] Failed to finalize policy: %s", self.name, e)
            return {
                "final_decision": "Error during policy making. Default to safe baseline.",
                "justification": "System error prevented full deliberation.",
                "execution_orders": ["Hold current posture."]
            }
