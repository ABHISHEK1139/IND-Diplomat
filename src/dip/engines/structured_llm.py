"""Structured LLM helpers for neuro-symbolic decision support.

The LLM may generate hypotheses and critique, but schemas and deterministic
gates decide what enters the pipeline.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("nextgen.structured_llm")

T = TypeVar("T", bound=BaseModel)

class LLMStructuredClient:
    """Phase 8: Centralized LLM client supporting local routing and structured outputs."""
    
    def __init__(self, model_name: str = None):
        from dip.core.Config.config import config
        self.model = model_name or config.LLM_MODEL
        self.provider = self._determine_provider(self.model)
        
        # Centralized API key management (routing based on provider)
        if self.provider == "openai":
            self.api_key = os.getenv("OPENAI_API_KEY", getattr(config, "OPENAI_API_KEY", ""))
        elif self.provider == "anthropic":
            self.api_key = os.getenv("ANTHROPIC_API_KEY", getattr(config, "ANTHROPIC_API_KEY", ""))
        elif self.provider == "ollama":
            self.api_key = "ollama"  # local API key not needed
        elif self.provider == "deepseek":
            self.api_key = os.getenv("DEEPSEEK_API_KEY", getattr(config, "DEEPSEEK_API_KEY", ""))
            if self.api_key:
                os.environ["DEEPSEEK_API_KEY"] = self.api_key
        else:
            self.api_key = os.getenv("LITELLM_API_KEY", "")

    def _determine_provider(self, model_name: str) -> str:
        """Route based on model prefix."""
        if model_name.startswith("gpt-"): return "openai"
        if model_name.startswith("claude-"): return "anthropic"
        if model_name.startswith("ollama/"): return "ollama"
        if model_name.startswith("deepseek/"): return "deepseek"
        if model_name.startswith("vllm/"): return "vllm"
        return "unknown"


def _strip_json_fence(content: str) -> str:
    text = str(content or "").strip()
    # Strip markdown fences if present
    if "```json" in text.lower():
        text = text.split("```json", 1)[1]
        text = text.split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1]
        text = text.split("```", 1)[0]
    
    # Try to find the outermost JSON object or array
    text = text.strip()
    first_brace = text.find('{')
    first_bracket = text.find('[')
    
    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        last_brace = text.rfind('}')
        if last_brace != -1:
            return text[first_brace:last_brace+1]
            
    if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
        last_bracket = text.rfind(']')
        if last_bracket != -1:
            return text[first_bracket:last_bracket+1]
            
    return text


def parse_model(content: str, output_model: Type[T]) -> T:
    """Parse and validate a model from LLM text."""

    payload = json.loads(_strip_json_fence(content))
    return output_model.model_validate(payload)


def json_schema_response_format(output_model: Type[BaseModel]) -> Dict[str, Any]:
    """LiteLLM/OpenAI-compatible strict JSON schema response format."""

    return {
        "type": "json_schema",
        "json_schema": {
            "name": output_model.__name__,
            "schema": output_model.model_json_schema(),
            "strict": True,
        },
    }


async def structured_acompletion(
    *,
    model: str,
    messages: List[Dict[str, str]],
    output_model: Type[T],
    temperature: float = 0.1,
    max_tokens: int = 1000,
) -> Optional[T]:
    """Return a validated Pydantic model or None.

    Preferred path: provider-native strict JSON schema through LiteLLM.
    Fallback: JSON-object mode and Pydantic validation. This leaves room for
    Instructor/Outlines without forcing those optional dependencies everywhere.
    """
    if os.getenv("FORCE_MINISTER_HEURISTIC") == "1":
        return None

    try:
        import litellm
    except Exception:
        return None

    try:
        import instructor
        INSTRUCTOR_AVAILABLE = True
    except ImportError:
        INSTRUCTOR_AVAILABLE = False

    client = LLMStructuredClient(model)

    if INSTRUCTOR_AVAILABLE and client.provider != "ollama":
        try:
            instructor_client = instructor.from_litellm(litellm.acompletion)
            response = await instructor_client.chat.completions.create(
                model=client.model,
                response_model=output_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                max_retries=3,
                api_key=client.api_key if client.api_key else None
            )
            return response
        except Exception as exc:
            logger.debug("Instructor structured LLM attempt failed: %s", exc)
            # Fall through to raw litellm attempts

    attempts = [
        {"response_format": json_schema_response_format(output_model)},
        {"response_format": {"type": "json_object"}},
        {},
    ]

    for kwargs in attempts:
        try:
            response = await litellm.acompletion(
                model=client.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=client.api_key if client.api_key else None,
                **kwargs,
            )
            content = response.choices[0].message.content
            return parse_model(content, output_model)
        except Exception as exc:
            logger.debug("Structured LLM attempt failed: %s", exc)
            continue

    # Fallback to Universal LangChain ChatModel (e.g. ChatOllama / Local GPU / Deterministic)
    try:
        from dip.engines.langchain_llm import get_chat_model
        from langchain_core.messages import HumanMessage, SystemMessage
        chat_model = get_chat_model(temperature=temperature)
        lc_msgs = []
        for m in messages:
            if m.get("role") == "system":
                lc_msgs.append(SystemMessage(content=m.get("content", "")))
            else:
                lc_msgs.append(HumanMessage(content=m.get("content", "")))
        res = await chat_model.ainvoke(lc_msgs)
        return parse_model(res.content, output_model)
    except Exception as exc:
        logger.debug("Universal LangChain ChatModel async structured fallback failed: %s", exc)

    return None


def structured_completion(
    *,
    model: str,
    messages: List[Dict[str, str]],
    output_model: Type[T],
    temperature: float = 0.1,
    max_tokens: int = 1000,
) -> Optional[T]:
    """Synchronous structured completion for non-async modules."""
    if os.getenv("FORCE_MINISTER_HEURISTIC") == "1":
        return None

    try:
        import litellm
    except Exception:
        return None

    try:
        import instructor
        INSTRUCTOR_AVAILABLE = True
    except ImportError:
        INSTRUCTOR_AVAILABLE = False

    client = LLMStructuredClient(model)

    if INSTRUCTOR_AVAILABLE and client.provider != "ollama":
        try:
            instructor_client = instructor.from_litellm(litellm.completion)
            response = instructor_client.chat.completions.create(
                model=client.model,
                response_model=output_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                max_retries=3,
                api_key=client.api_key if client.api_key else None
            )
            return response
        except Exception as exc:
            logger.debug("Instructor structured LLM attempt failed: %s", exc)
            # Fall through to raw litellm attempts

    attempts = [
        {"response_format": json_schema_response_format(output_model)},
        {"response_format": {"type": "json_object"}},
        {},
    ]

    for kwargs in attempts:
        try:
            response = litellm.completion(
                model=client.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=client.api_key if client.api_key else None,
                **kwargs,
            )
            content = response.choices[0].message.content
            return parse_model(content, output_model)
        except (ValidationError, json.JSONDecodeError) as exc:
            logger.debug("Structured LLM validation failed: %s", exc)
            continue
        except Exception as exc:
            logger.debug("Structured LLM provider attempt failed: %s", exc)
            continue

    # Fallback to Universal LangChain ChatModel (e.g. ChatOllama / Local GPU / Deterministic)
    try:
        from dip.engines.langchain_llm import get_chat_model
        from langchain_core.messages import HumanMessage, SystemMessage
        chat_model = get_chat_model(temperature=temperature)
        lc_msgs = []
        for m in messages:
            if m.get("role") == "system":
                lc_msgs.append(SystemMessage(content=m.get("content", "")))
            else:
                lc_msgs.append(HumanMessage(content=m.get("content", "")))
        res = chat_model.invoke(lc_msgs)
        return parse_model(res.content, output_model)
    except Exception as exc:
        logger.debug("Universal LangChain ChatModel sync structured fallback failed: %s", exc)

    return None


def optional_guardrail_stack_status() -> Dict[str, bool]:
    """Report whether stronger structured-output libraries are installed."""

    from importlib.util import find_spec

    return {
        "instructor": find_spec("instructor") is not None,
        "outlines": find_spec("outlines") is not None,
        "pydantic_ai": find_spec("pydantic_ai") is not None,
        "z3": find_spec("z3") is not None or find_spec("z3_solver") is not None,
        "pyDatalog": find_spec("pyDatalog") is not None,
        "nemoguardrails": find_spec("nemoguardrails") is not None,
    }
