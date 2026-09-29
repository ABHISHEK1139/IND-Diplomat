"""
LangChain Universal LLM Factory & Local Model Abstraction — DIP 2.0
Supports Cloud LLMs (OpenAI, Claude, Gemini) and Local LLMs (Ollama, vLLM, Llama.cpp)
with automatic fallback to a deterministic heuristic model when API keys are absent.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

logger = logging.getLogger("DIP.NextGen.LangChainLLM")


class DeterministicHeuristicChatModel(BaseChatModel):
    """
    Zero-dependency deterministic fallback chat model.
    Guarantees reliable execution of structured outputs, minister deliberations,
    and strategic narrative synthesis during offline testing or when cloud keys are unset.
    """
    
    model_name: str = "dip-heuristic-deterministic-v2"
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_text = messages[-1].content if messages else ""
        
        # Generate appropriate response based on prompt context
        if "deliberation" in last_text.lower() or "hypothesis" in last_text.lower():
            content = json.dumps({
                "stance": "HIGH_ALERT",
                "risk_score": 0.82,
                "confidence": 0.85,
                "primary_claim": "Significant escalation risk identified with high-confidence indicators.",
                "supporting_evidence": ["Military mobilization along border", "Heightened diplomatic rhetoric"],
                "recommended_action": "Deploy rapid response deterrence and initiate urgent diplomatic channels."
            })
        elif "narrative" in last_text.lower() or "executive" in last_text.lower():
            content = (
                "Strategic Intelligence Assessment: Multi-source analysis indicates active regional tension. "
                "Confidence is calibrated at high reliability with corroborated sensor signals. "
                "Primary operational recommendation is maintaining heightened deterrence while pursuing multilateral de-escalation."
            )
        else:
            content = json.dumps({
                "decision": "ALERT",
                "threat_level": "CRITICAL",
                "escalation_score": 0.78,
                "confidence": 0.80,
                "reasoning": "Corroborated evidence atoms satisfy epistemic verification criteria."
            })
            
        message = AIMessage(content=content)
        return ChatResult(generations=[ChatGeneration(message=message)])

    @property
    def _llm_type(self) -> str:
        return "dip_heuristic"


def get_chat_model(
    model_name: Optional[str] = None,
    temperature: float = 0.1,
) -> BaseChatModel:
    """
    Factory function returning the best available ChatModel:
    1. Cloud Model (OpenAI / Claude / Gemini) if API keys set
    2. Local Ollama if available
    3. Deterministic Heuristic Chat Model (Safe fallback)
    """
    if os.getenv("FORCE_MINISTER_HEURISTIC") == "1":
        return DeterministicHeuristicChatModel()
        
    # 1. OpenAI
    if os.getenv("OPENAI_API_KEY"):
        try:
            try:
                from langchain_openai import ChatOpenAI
            except ImportError:
                # Older langchain-community layout (<0.3).
                from langchain_community.chat_models import ChatOpenAI
            return ChatOpenAI(
                model=model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                temperature=temperature,
                api_key=os.getenv("OPENAI_API_KEY")
            )
        except Exception as e:
            logger.warning(f"Failed to initialize ChatOpenAI: {e}")

    # 2. Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            from langchain_community.chat_models import ChatAnthropic
            return ChatAnthropic(
                model=model_name or "claude-3-5-sonnet-20241022",
                temperature=temperature,
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
            )
        except Exception as e:
            logger.warning(f"Failed to initialize ChatAnthropic: {e}")

    # 3. Google Gemini
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            return ChatGoogleGenerativeAI(
                model=model_name or "gemini-1.5-flash",
                temperature=temperature,
                google_api_key=key
            )
        except Exception as e:
            logger.warning(f"Failed to initialize ChatGoogleGenerativeAI: {e}")

    # 4. OpenRouter (when explicitly configured; mirrors the litellm path)
    if os.getenv("OPENROUTER_API_KEY"):
        try:
            try:
                from langchain_openai import ChatOpenAI
            except ImportError:
                # Older langchain-community layout (<0.3).
                from langchain_community.chat_models import ChatOpenAI
            _or_model = model_name or os.getenv("OPENROUTER_MODEL", "")
            if _or_model.startswith("openrouter/"):
                _or_model = _or_model.split("openrouter/", 1)[1]
            return ChatOpenAI(
                model=_or_model or "openai/gpt-4o-mini",
                temperature=temperature,
                api_key=os.getenv("OPENROUTER_API_KEY"),
                base_url="https://openrouter.ai/api/v1",
            )
        except Exception as e:
            logger.warning(f"Failed to initialize OpenRouter chat model: {e}")

    # 5. Local Ollama (auto-detect if running or configured)
    ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    try:
        import json as _json
        import urllib.request

        from dip.core.url_guard import require_http_scheme

        # OLLAMA_HOST is environment-supplied; require http(s) so urlopen cannot
        # be steered into file:// or other local schemes.
        tags_url = require_http_scheme(f"{ollama_host.rstrip('/')}/api/tags")
        with urllib.request.urlopen(tags_url, timeout=0.8) as resp:  # nosec B310 - scheme validated by require_http_scheme
            available = set()
            if resp.status == 200:
                try:
                    available = {m.get("name", "") for m in _json.load(resp).get("models", [])}
                except Exception:
                    available = set()
        from dip.core.Config.config import config as _config

        _configured = (model_name or _config.LLM_MODEL or "").strip()
        if _configured.startswith("ollama/"):
            _configured = _configured.split("ollama/", 1)[1]
            m_name = _configured
        else:
            m_name = model_name or os.getenv("OLLAMA_MODEL", "")
        # Never request a model the server does not have: a reachable host
        # with a missing model used to surface as a late 404. Fall through
        # to the deterministic model instead.
        if m_name and m_name in available:
            from langchain_ollama import ChatOllama
            logger.info(f"Using Live Local Ollama AI Model: {m_name} at {ollama_host}")
            return ChatOllama(
                model=m_name,
                base_url=ollama_host,
                temperature=temperature
            )
        if m_name:
            logger.debug(f"Ollama model '{m_name}' not present; skipping local backend.")
    except Exception as e:
        logger.debug(f"Local Ollama not reachable: {e}")

    # 6. Default Deterministic Fallback
    return DeterministicHeuristicChatModel()
