"""
Devil's Advocate
================
A specialized agent designed entirely to find flaws, missing evidence,
contradictions, and alternative explanations.
It never agrees with the consensus.
"""

import logging
import json
from dip.core.json_utils import strip_markdown_json, safe_parse_json
from typing import List, Dict, Any

from dip.core.Config.config import config
from dip.telemetry.llm_tracer import tracer

logger = logging.getLogger("Layer4.DevilsAdvocate")


class DevilsAdvocate:
    def __init__(self):
        self.model = config.LLM_MODEL

    async def critique(self, consensus_hypothesis: str, world_model, topic: str) -> Dict[str, Any]:
        """
        Attempts to dismantle the leading consensus hypothesis.
        """
        beliefs = world_model.get_beliefs_about(topic, max_hops=2)
        graph_context = "\n".join([f"- {b.get('head')} {b.get('type')} {b.get('tail')}" for b in beliefs[:50]])

        prompt = (
            "You are the Devil's Advocate. Your ONLY job is to dismantle the following hypothesis.\n"
            "Find flaws, missing evidence, logical leaps, and alternative explanations.\n"
            "Do NOT agree with the hypothesis under any circumstances.\n\n"
            f"Consensus Hypothesis: {consensus_hypothesis}\n\n"
            f"Knowledge Graph Context:\n{graph_context}\n\n"
            "Output JSON matching exactly this schema:\n"
            "{\n"
            "  \"flaws_identified\": [\"string\"],\n"
            "  \"alternative_explanation\": \"string\",\n"
            "  \"contradictory_evidence_needed\": [\"string\"]\n"
            "}"
        )

        try:
            response = await tracer.acompletion(
                layer="Layer4_DevilsAdvocate",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            content = strip_markdown_json(content)
                
            return json.loads(content)
        except Exception as e:
            logger.error(f"Devil's Advocate failed: {e}")
            return {"flaws_identified": [], "alternative_explanation": f"Failed to run: {e}", "contradictory_evidence_needed": []}
