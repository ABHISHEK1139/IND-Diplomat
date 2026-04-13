"""
Investigation controller (orchestration layer).

This module sits above Layer-3 and coordinates investigation workflow:
query analysis -> retrieval planning -> iterative investigation.
"""

from __future__ import annotations

from typing import Any, Optional

from .research_controller import (
    ResearchController,
    QueryAnalysis,
    RetrievalPlan,
    EvidenceBundle,
    research_controller,
)
from .investigation_loop import (
    InvestigationLoop,
    InvestigationResult,
    investigation_loop,
)


class InvestigationController:
    """Controller facade for research + investigation execution."""

    def __init__(
        self,
        controller: Optional[ResearchController] = None,
        loop: Optional[InvestigationLoop] = None,
    ):
        self._controller = controller or research_controller
        self._loop = loop or investigation_loop

    def analyze_query(self, query: str) -> QueryAnalysis:
        return self._controller.analyze_query(query)

    def create_retrieval_plan(self, analysis: QueryAnalysis) -> RetrievalPlan:
        return self._controller.create_retrieval_plan(analysis)

    async def execute_retrieval(
        self,
        plan: RetrievalPlan,
        retriever: Any = None,
    ) -> EvidenceBundle:
        return await self._controller.execute_retrieval(plan, retriever=retriever)

    async def investigate(
        self,
        query: str,
        retriever: Any = None,
        max_rounds: int = 3,
        context: Any = None,
    ) -> InvestigationResult:
        return await self._loop.investigate(
            query=query,
            retriever=retriever,
            max_rounds=max_rounds,
            context=context,
        )


investigation_controller = InvestigationController()

__all__ = ["InvestigationController", "investigation_controller"]
