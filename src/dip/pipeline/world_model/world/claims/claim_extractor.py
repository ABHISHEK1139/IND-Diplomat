"""
Claim Extractor
================
Routes to a small, fast local LLM (e.g., Qwen 3 4B or Gemma 3 4B)
to isolate distinct assertions from textual evidence and attach
confidence values.
"""

import json
import logging
from typing import List, Dict, Any

from dip.core.Config.config import config
from dip.core.json_utils import strip_markdown_json
from dip.telemetry.llm_tracer import tracer

logger = logging.getLogger("Layer3.ClaimExtractor")


class ClaimExtractor:
    """
    Extracts individual claims from an observation to populate the World Model.
    """

    def __init__(self, model_name: str = "ollama/qwen2.5:3b"):
        self.model_name = model_name

    def extract(self, text: str, source_context: str = "") -> List[Dict[str, Any]]:
        """
        Extracts structured claims.
        """
        prompt = f"""You are an intelligence analyst extracting factual claims from a text.
Isolate exactly 1 to 3 distinct factual claims from the following text.
Each claim must have a Subject, Predicate, and Object.

Source Context: {source_context}
Text: "{text[:1500]}"

Return ONLY a JSON array of objects:
[
  {{
    "subject": "Entity",
    "predicate": "Action/Relation",
    "object": "Target Entity/Value",
    "time": "When (if stated)",
    "confidence_extracted": 0.0 to 1.0
  }}
]
"""
        try:
            response = tracer.completion_sync(
                layer="Layer3_ClaimExtractor",
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = strip_markdown_json(response.choices[0].message.content)
                
            data = json.loads(content)
            
            # Handle if the LLM wraps it in a dict {"claims": [...]}
            if isinstance(data, dict):
                claims = data.get("claims", list(data.values())[0])
            else:
                claims = data
                
            logger.info(f"Extracted {len(claims)} claims.")
            return claims
            
        except Exception as e:
            logger.error(f"Failed claim extraction with small model {self.model_name}: {e}. Falling back.")
            try:
                # Fallback to main API model
                response = tracer.completion_sync(
                    layer="Layer3_ClaimExtractor",
                    model=config.LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                content = strip_markdown_json(response.choices[0].message.content)
                data = json.loads(content)
                if isinstance(data, dict):
                    return data.get("claims", list(data.values())[0])
                return data
            except Exception as inner_e:
                logger.error(f"Fallback claim extraction failed: {inner_e}")
                return []
