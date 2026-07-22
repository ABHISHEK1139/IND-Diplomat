"""
Query Generator — Dynamic Search Query Generation
===================================================

Instead of searching "AI", the planner generates targeted queries like:
    "India AI policy 2025"
    "Indian semiconductor roadmap"
    "NVIDIA India manufacturing"
    "AI patents India 2024-2025"

Uses LLM to generate domain-specific, high-retrieval queries.
"""

import json
import logging
from typing import Dict, List

from dip.Config.config import config
from dip.core.json_utils import strip_markdown_json
from dip.core.schema import Investigation
from dip.layer10_telemetry.llm_tracer import tracer

logger = logging.getLogger("Layer1.QueryGenerator")


class QueryGenerator:
    """
    Generates targeted search queries based on the investigation's scope.

    Returns a dict mapping source categories to query lists.
    """

    def __init__(self):
        self.model = config.LLM_MODEL

    def generate(self, investigation: Investigation) -> Dict[str, List[str]]:
        """
        Generate search queries for each relevant source category.

        Returns:
            {"News": ["query1", ...], "Research": ["query2", ...], ...}
        """
        scope = investigation.scope
        objective = investigation.objective

        prompt = f"""You are a search query strategist for an intelligence analysis platform.

Investigation: {investigation.title}
Objective: {objective.objective}
Countries: {', '.join(scope.countries) if scope.countries else 'Global'}
Domains: {', '.join(scope.domains) if scope.domains else 'General'}
Companies: {', '.join(scope.companies) if scope.companies else 'None'}
Government Bodies: {', '.join(scope.government_bodies) if scope.government_bodies else 'None'}
Key Actors: {', '.join(scope.key_actors) if scope.key_actors else 'None'}
Keywords: {', '.join(scope.keywords) if scope.keywords else 'None'}
Time Horizon: {objective.time_horizon}

Generate targeted search queries optimized for different source types.
Each query should be specific enough to return high-quality results.

Return a JSON object:
{{
    "News": ["query1", "query2", "query3", "query4", "query5"],
    "Research": ["query1", "query2", "query3"],
    "Economic": ["query1", "query2", "query3"],
    "Government": ["query1", "query2"],
    "Technology": ["query1", "query2", "query3"]
}}

Generate 3-5 queries per category. Only include categories relevant to this investigation.
Each query should be 3-8 words, optimized for search engines.
Output ONLY valid JSON."""

        try:
            response = tracer.completion_sync(
                layer="Layer1_QueryGenerator",
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            content = strip_markdown_json(response.choices[0].message.content)

            queries = json.loads(content)
            total = sum(len(v) for v in queries.values())
            logger.info(f"Generated {total} search queries across {len(queries)} categories")
            return queries

        except Exception as e:
            logger.error(f"Query generation failed: {e}. Using fallback queries.")
            return self._fallback_queries(investigation)

    def _fallback_queries(self, investigation: Investigation) -> Dict[str, List[str]]:
        """Generate basic queries without LLM."""
        scope = investigation.scope
        base_terms = scope.keywords[:3] if scope.keywords else [investigation.title]
        countries = scope.countries[:2] if scope.countries else []

        queries = {"News": [], "Research": []}
        for term in base_terms:
            for country in countries:
                queries["News"].append(f"{country} {term}")
            queries["Research"].append(term)

        if not queries["News"]:
            queries["News"] = [investigation.title]

        return queries
