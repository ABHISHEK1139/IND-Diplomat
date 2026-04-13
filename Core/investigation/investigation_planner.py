"""
Investigation planner for generating targeted research queries.

This bridge component uses the shared LLM gateway for planner prompts.
"""

from __future__ import annotations

from typing import List
import os
import re

from Config.config import LLM_MODEL, LLM_PROVIDER, OPENROUTER_MODEL
from engine.Layer4_Analysis.core.llm_client import LocalLLM


def call_planner_llm(prompt: str) -> str:
    """
    Call the shared LLM gateway to generate research queries.
    """
    provider_name = str(os.getenv("INVESTIGATION_PLANNER_PROVIDER", LLM_PROVIDER or "ollama")).strip()
    default_model = OPENROUTER_MODEL if provider_name.lower() == "openrouter" else LLM_MODEL
    model_name = str(os.getenv("INVESTIGATION_PLANNER_MODEL", default_model or "deepseek-r1:7b")).strip()
    timeout_s = int(os.getenv("INVESTIGATION_PLANNER_TIMEOUT_SEC", "45"))
    planner_max_tokens_raw = str(os.getenv("INVESTIGATION_PLANNER_MAX_TOKENS", "")).strip()
    planner_max_tokens = int(planner_max_tokens_raw) if planner_max_tokens_raw else None
    llm = LocalLLM(model=model_name, provider=provider_name)

    try:
        result = llm.generate(
            system_prompt="You create concise evidence-collection search queries.",
            user_prompt=prompt,
            temperature=0.1,
            timeout=max(5, timeout_s),
            max_tokens=planner_max_tokens,
        )
        return "" if str(result).startswith("LLM_ERROR:") else str(result)
    except Exception:
        return ""


def generate_queries(question: str, gaps: List[str], max_queries: int = 6) -> List[str]:
    """
    Generate 3-6 search queries to fill specific evidence gaps.
    """
    prompt = f"""
You are a research planning assistant.

Your job: create web search queries to collect missing evidence.

Question:
{question}

Missing evidence categories:
{gaps}

Rules:
- DO NOT explain anything
- DO NOT answer the question
- ONLY produce search queries
- Prefer official sources (government, ministry, treaties)

Output:
3 to 6 search queries only.
""".strip()

    raw = call_planner_llm(prompt)
    queries = _parse_queries(raw)
    if len(queries) < 3:
        queries = _fallback_queries(question, gaps)

    deduped: List[str] = []
    for query in queries:
        q = " ".join(str(query or "").split()).strip()
        if not q:
            continue
        key = q.lower()
        if key in {item.lower() for item in deduped}:
            continue
        deduped.append(q)

    if not deduped:
        deduped = _fallback_queries(question, gaps)

    max_queries = max(3, min(6, int(max_queries)))
    return deduped[:max_queries]


def _parse_queries(raw: str) -> List[str]:
    lines = [line.strip() for line in str(raw or "").splitlines() if line.strip()]
    queries: List[str] = []
    for line in lines:
        line = re.sub(r"^\s*[-*]\s*", "", line)
        line = re.sub(r"^\s*\d+\.\s*", "", line)
        line = line.strip().strip('"').strip("'")
        if not line:
            continue
        if len(line.split()) < 3:
            continue
        queries.append(line)
    return queries


def _fallback_queries(question: str, gaps: List[str]) -> List[str]:
    base = _topic_hint(question)
    queries: List[str] = []

    if "legal" in gaps:
        queries.extend([
            f"{base} foreign ministry sovereignty statement site:gov",
            f"{base} one china principle official statement",
            f"{base} security commitment press release state department",
        ])
    if "military" in gaps:
        queries.extend([
            f"{base} military exercise announcement official",
            f"{base} defense ministry warning statement",
        ])
    if "diplomatic" in gaps:
        queries.extend([
            f"{base} diplomatic talks official readout",
            f"{base} ministry of foreign affairs briefing",
        ])
    if "economic" in gaps:
        queries.extend([
            f"{base} sanctions announcement official gazette",
            f"{base} trade restriction official notice",
        ])
    if "alliances" in gaps:
        queries.extend([
            f"{base} alliance security commitment treaty statement",
            f"{base} bilateral defense commitment official release",
        ])

    if len(queries) < 3:
        queries.extend(
            [
                f"{base} official statement latest",
                f"{base} ministry briefing transcript",
                f"{base} legal position government statement",
            ]
        )
    return queries[:6]


def _topic_hint(question: str) -> str:
    text = str(question or "").strip()
    if not text:
        return "geopolitical tension"
    return text.rstrip("?")


__all__ = ["call_planner_llm", "generate_queries"]
