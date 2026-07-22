"""
Hypothesis Generator
====================
Instead of a single confident answer, generates multiple probabilistic hypotheses
(H1, H2, H3) with supporting and opposing evidence.
"""

import logging
import json
from dip.core.json_utils import strip_markdown_json, safe_parse_json
from typing import List, Dict, Any

from dip.Config.config import config
from dip.layer10_telemetry.llm_tracer import tracer

logger = logging.getLogger("Layer4.HypothesisGenerator")


class HypothesisGenerator:
    def __init__(self):
        self.model = config.LLM_MODEL

    async def generate_hypotheses(self, consensus_text: str, world_model, topic: str) -> List[Dict[str, Any]]:
        """
        Takes the consensus and splits it into multiple probable paths.
        """
        beliefs = world_model.get_beliefs_about(topic, max_hops=1)
        graph_context = "\n".join([f"- {b.get('head')} {b.get('type')} {b.get('tail')}" for b in beliefs[:30]])

        prompt = (
            "Based on the following consensus and knowledge graph context, generate 3 distinct, "
            "probabilistic hypotheses (H1, H2, H3).\n"
            "Include supporting evidence and opposing evidence for each.\n\n"
            f"Consensus:\n{consensus_text}\n\n"
            f"Context:\n{graph_context}\n\n"
            "Output JSON exactly matching this schema:\n"
            "{\n"
            "  \"hypotheses\": [\n"
            "    {\n"
            "      \"id\": \"H1\",\n"
            "      \"description\": \"Economic slowdown\",\n"
            "      \"probability\": 0.58,\n"
            "      \"supporting_evidence\": [\"Claim A\"],\n"
            "      \"opposing_evidence\": [\"Claim B\"]\n"
            "    }\n"
            "  ]\n"
            "}"
        )

        try:
            response = await tracer.acompletion(
                layer="Layer4_HypothesisGenerator",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            content = strip_markdown_json(content)
                
            data = json.loads(content)
            return data.get("hypotheses", [])
        except Exception as e:
            logger.error(f"Hypothesis Generator failed: {e}")
            return []
