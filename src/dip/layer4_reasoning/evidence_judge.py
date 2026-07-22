"""
Evidence Judge
===============
A Tier 2 (Qwen 3 4B) module that verifies if an expert's claim 
is actually backed by evidence in the World Model.
"""

import logging
from typing import Dict, Any

from dip.Config.config import config
from dip.layer10_telemetry.llm_tracer import tracer

logger = logging.getLogger("Layer4.EvidenceJudge")


class EvidenceJudge:
    """
    Validates claims against the known World Model graph.
    """
    def __init__(self, model_name: str = "ollama/qwen2.5:3b"):
        self.model_name = model_name

    async def judge_claim(self, claim: str, world_model, topic: str) -> str:
        """
        Outputs YES, NO, or PARTIAL.
        """
        beliefs = world_model.get_beliefs_about(topic, max_hops=1)
        graph_context = "\n".join([f"- {b.get('head')} {b.get('type')} {b.get('tail')}" for b in beliefs[:20]])
        
        prompt = (
            "You are a strict Evidence Judge.\n"
            f"Determine if the following claim is supported by the provided Knowledge Graph context.\n\n"
            f"Claim: {claim}\n\n"
            f"Context:\n{graph_context}\n\n"
            "Reply strictly with 'YES', 'NO', or 'PARTIAL' and nothing else."
        )

        try:
            response = await tracer.acompletion(
                layer="Layer4_EvidenceJudge",
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            judgment = response.choices[0].message.content.strip().upper()
            if "YES" in judgment: return "YES"
            if "PARTIAL" in judgment: return "PARTIAL"
            return "NO"
        except Exception as e:
            logger.error(f"Evidence Judge failed: {e}")
            return "PARTIAL"  # Fallback to uncertainty
