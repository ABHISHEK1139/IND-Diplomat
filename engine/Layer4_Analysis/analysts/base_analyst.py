import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

from engine.Layer4_Analysis.core.llm_client import llm_client
from engine.Layer3_StateModel.schemas.state_context import StateContext

logger = logging.getLogger(__name__)

class BaseAnalyst(ABC):
    """
    Base class for Domain-Specific Analysts.
    They process the raw StateContext before the council convenes,
    extracting insights specific to their domain.
    """
    def __init__(self, name: str):
        self.name = name

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        pass

    async def analyze(self, state_context: StateContext) -> Dict[str, Any]:
        """
        Runs the analyst LLM over the state context to produce a structured JSON report.
        """
        logger.info("[%s] Running domain analysis...", self.name)
        
        # Serialize state context safely
        ctx_dict = {}
        if hasattr(state_context, "to_dict"):
            ctx_dict = state_context.to_dict()
        else:
            try:
                ctx_dict = json.loads(json.dumps(state_context, default=lambda o: getattr(o, '__dict__', str(o))))
            except Exception:
                ctx_dict = {"raw_str": str(state_context)}
                
        prompt = (
            f"Analyze the following StateContext from the perspective of the {self.name}.\n"
            "Extract the most critical insights, anomalies, and warning indicators relevant to your domain.\n\n"
            f"STATE CONTEXT:\n{json.dumps(ctx_dict, indent=2)}\n\n"
            "Respond in valid JSON format ONLY with the following keys:\n"
            '- "key_findings": List of strings (max 3).\n'
            '- "risk_score": Float between 0.0 and 1.0 representing domain-specific escalation risk.\n'
            '- "anomalies": List of strings detailing any strange or contradictory signals in your domain.\n'
            '- "domain_summary": A one-paragraph summary of your assessment.'
        )

        try:
            response = await llm_client.generate(
                prompt,
                system_prompt=self.system_prompt,
                json_mode=True
            )
            # Try parsing the JSON
            import re
            
            # Clean up markdown fences if they exist
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
                
            report = json.loads(cleaned.strip())
            logger.info("[%s] Analysis complete. Risk Score: %s", self.name, report.get("risk_score"))
            return report
        except Exception as e:
            logger.error("[%s] Failed to run analysis: %s", self.name, e)
            return {
                "key_findings": ["Analysis failed due to error."],
                "risk_score": 0.5,
                "anomalies": [],
                "domain_summary": "Error during analysis execution."
            }
