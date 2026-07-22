"""
Objective Parser — Investigation Intent Classification
======================================================

Parses the user's raw question into structured objective categories
(Prediction, Policy Analysis, Risk Analysis, etc.)

Intended to route to a small, fast local LLM (e.g., Qwen 3 4B).
"""

import json
import logging
from typing import Dict, Any

from dip.Config.config import config
from dip.core.json_utils import strip_markdown_json
from dip.layer10_telemetry.llm_tracer import tracer

logger = logging.getLogger("Layer0.ObjectiveParser")


class ObjectiveParser:
    """
    Parses user queries into structured objectives using a small LLM.
    """

    def __init__(self, small_model: str = "ollama/qwen2.5:3b"):
        # We try to use a small local model if available, otherwise fallback
        # to the main system model.
        self.model = small_model

    def parse(self, query: str) -> Dict[str, Any]:
        """
        Classifies the query into an objective.
        """
        prompt = f"""You are an intelligence objective parser.
Classify the following user question into a structured objective.

Question: "{query}"

Determine:
1. Decision Support Type (Prediction, Comparison, Monitoring, Policy Analysis, Risk Analysis, Historical Review)
2. Time Horizon (e.g., 1 Year, 5 Years, 10 Years, Ongoing)
3. Depth (Brief, Standard, Research, Comprehensive)

Return ONLY a JSON object:
{{
    "objective": "A clear, active rephrasing of the goal",
    "decision_support_type": "...",
    "time_horizon": "...",
    "depth": "..."
}}
"""
        try:
            response = tracer.completion_sync(
                layer="Layer0_ObjectiveParser",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = strip_markdown_json(response.choices[0].message.content)
            
            parsed = json.loads(content)
            logger.info(f"Parsed objective: {parsed['decision_support_type']} | {parsed['time_horizon']}")
            return parsed
            
        except Exception as e:
            logger.error(f"Failed with small model {self.model}: {e}. Falling back to main model.")
            # Fallback to main model
            try:
                response = tracer.completion_sync(
                    layer="Layer0_ObjectiveParser",
                    model=config.LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                content = strip_markdown_json(response.choices[0].message.content)
                parsed = json.loads(content)
                return parsed
            except Exception as inner_e:
                logger.error(f"Fallback also failed: {inner_e}")
                return {
                    "objective": query,
                    "decision_support_type": "Strategic Assessment",
                    "time_horizon": "Unknown",
                    "depth": "Research"
                }
