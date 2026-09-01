import logging
import os
import time
import uuid
import asyncio
from typing import Any
from datetime import datetime, timezone
import contextvars

try:
    import litellm
    # Langfuse is optional. Enabling its callback without credentials prevents
    # every local Ollama request from reaching the model.
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]
    else:
        logger = logging.getLogger("Layer10.LLMTracer")
        logger.info("Langfuse credentials are not configured; cloud tracing is disabled.")
except ImportError:
    litellm = None

from dip.core.schema import ReasoningTrace
from dip.pipeline.memory.core.investigation_memory import InvestigationMemory

logger = logging.getLogger("Layer10.LLMTracer")

# Context variable to hold the current investigation ID
current_investigation_id = contextvars.ContextVar("current_investigation_id", default=None)

class LLMTracer:
    """
    Intercepts and logs every LLM call as a ReasoningTrace to generate training data.
    """
    def __init__(self):
        self.memory = InvestigationMemory()

    @staticmethod
    def _provider_kwargs(model: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Translate provider-incompatible request options before dispatch."""
        request_kwargs = dict(kwargs)
        if model.startswith("ollama/"):
            # This LiteLLM/Ollama adapter misclassifies JSON-mode requests as
            # tool calls and fails before the request reaches the local model.
            # Prompts already require JSON; retain that contract without sending
            # the incompatible OpenAI-only option.
            request_kwargs.pop("response_format", None)
            request_kwargs.pop("format", None)
            request_kwargs.setdefault("api_base", os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
        return request_kwargs

    async def acompletion(self, layer: str, model: str, messages: list, **kwargs) -> Any:
        if not litellm:
            raise RuntimeError("litellm is not installed.")
            
        start_time = time.time()
        prompt_text = str(messages)
        request_kwargs = self._provider_kwargs(model, kwargs)
        
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                **request_kwargs
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            output_text = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens if hasattr(response, "usage") and response.usage else 0
            output_tokens = response.usage.completion_tokens if hasattr(response, "usage") and response.usage else 0
            
            cost = 0.0
            try:
                cost = litellm.completion_cost(response)
            except Exception:
                pass
                
            trace = ReasoningTrace(
                trace_id=f"TRC-{uuid.uuid4().hex[:8].upper()}",
                layer=layer,
                model_used=model,
                prompt=prompt_text,
                context=request_kwargs.get("system_prompt", "N/A"),
                output=output_text,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
            inv_id = current_investigation_id.get()
            if inv_id:
                inv = self.memory.get_investigation(inv_id)
                if inv:
                    inv.reasoning_traces.append(trace)
                    self.memory.save_investigation(inv)
                
            return response
            
        except Exception as e:
            logger.debug(f"LiteLLM call failed ({e}), falling back to Universal LangChain model...")
            try:
                from dip.engines.langchain_llm import get_chat_model
                from langchain_core.messages import HumanMessage, SystemMessage
                chat_model = get_chat_model()
                lc_msgs = []
                for m in messages:
                    if isinstance(m, dict):
                        if m.get("role") == "system":
                            lc_msgs.append(SystemMessage(content=m.get("content", "")))
                        else:
                            lc_msgs.append(HumanMessage(content=m.get("content", "")))
                    else:
                        lc_msgs.append(HumanMessage(content=str(m)))
                res = await chat_model.ainvoke(lc_msgs)
                
                class MockMsg:
                    def __init__(self, c): self.content = c
                class MockCh:
                    def __init__(self, c): self.message = MockMsg(c)
                class MockResp:
                    def __init__(self, c):
                        self.choices = [MockCh(c)]
                        self.usage = None
                return MockResp(res.content)
            except Exception as inner_exc:
                logger.error(f"LLM Call failed during trace and fallback: {inner_exc}")
                raise

    def completion_sync(self, layer: str, model: str, messages: list, **kwargs) -> Any:
        if not litellm:
            raise RuntimeError("litellm is not installed.")
            
        start_time = time.time()
        prompt_text = str(messages)
        request_kwargs = self._provider_kwargs(model, kwargs)
        
        try:
            response = litellm.completion(
                model=model,
                messages=messages,
                **request_kwargs
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            output_text = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens if hasattr(response, "usage") and response.usage else 0
            output_tokens = response.usage.completion_tokens if hasattr(response, "usage") and response.usage else 0
            
            cost = 0.0
            try:
                cost = litellm.completion_cost(response)
            except Exception:
                pass
                
            trace = ReasoningTrace(
                trace_id=f"TRC-{uuid.uuid4().hex[:8].upper()}",
                layer=layer,
                model_used=model,
                prompt=prompt_text,
                context=request_kwargs.get("system_prompt", "N/A"),
                output=output_text,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
            inv_id = current_investigation_id.get()
            if inv_id:
                inv = self.memory.get_investigation(inv_id)
                if inv:
                    inv.reasoning_traces.append(trace)
                    self.memory.save_investigation(inv)
                
            return response
            
        except Exception as e:
            logger.debug(f"LiteLLM sync call failed ({e}), falling back to Universal LangChain model...")
            try:
                from dip.engines.langchain_llm import get_chat_model
                from langchain_core.messages import HumanMessage, SystemMessage
                chat_model = get_chat_model()
                lc_msgs = []
                for m in messages:
                    if isinstance(m, dict):
                        if m.get("role") == "system":
                            lc_msgs.append(SystemMessage(content=m.get("content", "")))
                        else:
                            lc_msgs.append(HumanMessage(content=m.get("content", "")))
                    else:
                        lc_msgs.append(HumanMessage(content=str(m)))
                res = chat_model.invoke(lc_msgs)
                
                class MockMsg:
                    def __init__(self, c): self.content = c
                class MockCh:
                    def __init__(self, c): self.message = MockMsg(c)
                class MockResp:
                    def __init__(self, c):
                        self.choices = [MockCh(c)]
                        self.usage = None
                return MockResp(res.content)
            except Exception as inner_exc:
                logger.error(f"LLM Call failed during sync trace and fallback: {inner_exc}")
                raise
            
# Global singleton instance
tracer = LLMTracer()
