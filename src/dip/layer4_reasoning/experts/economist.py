"""
Economist Expert
================
Domain expert for macroeconomics, trade, and industrial policy.
"""

import logging
import json
from dip.core.json_utils import strip_markdown_json, safe_parse_json
from typing import Dict, Any

from dip.layer4_reasoning.experts.base import BaseExpert
from dip.layer10_telemetry.llm_tracer import tracer
from dip.core.schema import MinisterHypothesisOutput

logger = logging.getLogger("Layer4.Experts.Economist")


class EconomistExpert(BaseExpert):
    def __init__(self):
        super().__init__(name="Economist", expertise="Macroeconomics, Industrial Policy, and Trade")

    async def analyze(self, world_model, topic: str) -> MinisterHypothesisOutput:
        beliefs = world_model.get_beliefs_about(topic, max_hops=2)
        lessons = self.recall_lessons(topic)

        graph_context = "Economic Indicators & Entities:\n"
        for b in beliefs[:50]:
            graph_context += f"- {b.get('head')} [{b.get('type')}] {b.get('tail')}\n"

        prompt = (
            f"You are the {self.name}, an expert in {self.expertise}.\n"
            f"Analyze this topic: {topic}\n\n"
            f"{lessons}\n"
            f"{graph_context}\n"
            "Provide your hypothesis as a JSON object matching this schema:\n"
            "{\n"
            "  \"predicted_signals\": [\"Event A\"],\n"
            "  \"matched_signals\": [\"Claim B\"],\n"
            "  \"missing_signals\": [\"Evidence C\"],\n"
            "  \"confidence\": 0.85,\n"
            "  \"rationale\": \"string\"\n"
            "}"
        )

        try:
            response = await tracer.acompletion(
                layer=f"Layer4_{self.name}",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            
            content = strip_markdown_json(content)
                
            data = json.loads(content)
            return MinisterHypothesisOutput(minister=self.name, **data)
            
        except Exception as e:
            logger.error(f"{self.name} failed to analyze: {e}")
            return MinisterHypothesisOutput(minister=self.name, rationale=f"Error: {e}")
