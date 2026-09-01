"""
Missing Evidence Detector
===========================

Analyzes a collection round's output against the CollectionPlan to determine
what information is still missing, updating the search needs dynamically.
Routes to a small, fast local LLM (e.g., Qwen 3 4B).
"""

import logging
from typing import List

from dip.core.Config.config import config
from dip.core.schema import Investigation, RawObservation
from dip.telemetry.llm_tracer import tracer

logger = logging.getLogger("Layer1.MissingEvidence")


class MissingEvidenceDetector:
    """
    Identifies gaps in collected evidence.
    """

    def __init__(self, small_model: str = "ollama/qwen2.5:3b"):
        self.model = small_model

    def detect(self, investigation: Investigation, observations: List[RawObservation]) -> List[str]:
        """
        Determines what is missing and returns a list of new targeted queries.
        """
        if not observations:
            return ["General overview"]
            
        # Summarize what we have
        sources_found = set(obs.source_type for obs in observations)
        
        prompt = f"""You are an intelligence gap analyst.
Objective: {investigation.objective.objective if investigation.objective else investigation.title}

We have collected evidence from these source types: {', '.join(sources_found)}
Total observations collected so far: {len(observations)}

Identify exactly 3 specific pieces of missing evidence or data points we still need to fulfill the objective.
Return ONLY a comma-separated list of 3 short search queries. No introductory text.
"""
        try:
            response = tracer.completion_sync(
                layer="Layer1_MissingEvidence",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            content = response.choices[0].message.content
            queries = [q.strip() for q in content.split(",") if q.strip()]
            logger.info(f"Missing evidence detected. New queries: {queries}")
            return queries
        except Exception as e:
            logger.error(f"Missing evidence detection failed: {e}")
            # Fallback to main model
            try:
                response = tracer.completion_sync(
                    layer="Layer1_MissingEvidence",
                    model=config.LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                content = response.choices[0].message.content
                queries = [q.strip() for q in content.split(",") if q.strip()]
                return queries
            except Exception as inner_e:
                logger.error(f"Fallback missing evidence failed: {inner_e}")
                return []
