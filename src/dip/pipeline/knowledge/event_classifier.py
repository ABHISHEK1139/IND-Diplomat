from dip.core.Config.config import config
"""
Event Classifier (Layer 2)
==========================
Uses LLM to semantically classify events by domain.
"""

import os
import json
import logging
from typing import Tuple

try:
    import litellm
except ImportError:
    litellm = None

from dotenv import load_dotenv
from dip.core.json_utils import strip_markdown_json

load_dotenv()

logger = logging.getLogger("Layer2.event_classifier")
LLM_MODEL = config.LLM_MODEL

async def classify_event(text: str) -> Tuple[str, float]:
    """Returns (domain, confidence). Uses LLM for semantic classification."""
    if litellm is None:
        return "unknown", 0.0
        
    prompt = (
        f"Classify the following event text into exactly one of these geopolitical domains: "
        f"[military, diplomatic, economic, internal].\n\n"
        f"Text: '{text}'\n\n"
        f"Return ONLY a JSON object with 'domain' (string) and 'confidence' (float 0.0 to 1.0)."
    )

    try:
        response = await litellm.acompletion(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        
        raw = strip_markdown_json(response.choices[0].message.content)
        parsed = json.loads(raw)
        
        domain = parsed.get("domain", "unknown").lower()
        confidence = float(parsed.get("confidence", 0.5))
        
        if domain not in ["military", "diplomatic", "economic", "internal"]:
            domain = "unknown"
            
        return domain, confidence
        
    except Exception as e:
        logger.error(f"Event classification failed: {e}")
        return "unknown", 0.0
