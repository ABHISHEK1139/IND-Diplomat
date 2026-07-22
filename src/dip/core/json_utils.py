"""Shared JSON extraction utilities for DIP 2.0."""
import re
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def strip_markdown_json(raw: str) -> str:
    """Extract JSON from markdown-fenced LLM output.
    
    Handles formats like:
      ```json\n{...}\n```
      ```{...}```
      raw JSON string
    """
    if not raw:
        return raw
    raw = raw.strip()
    match = re.search(r'```(?:json)?\s*(.*?)```', raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw


def safe_parse_json(raw: str, default: Any = None, context: str = "") -> Any:
    """Parse JSON from potentially markdown-wrapped LLM output.
    
    Returns `default` on failure instead of raising.
    """
    cleaned = strip_markdown_json(raw)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("JSON parse failed%s: %s", f" ({context})" if context else "", e)
        return default
