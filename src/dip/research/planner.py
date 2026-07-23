"""
Politiq AI — Research Planner
=============================

End-to-End Orchestrator that takes a high-level goal or missing signals,
generates a ResearchRequest, runs the RetrievalPipeline, runs the 
VerificationPipeline, and returns a ResearchResult.
"""

import time
import uuid
import logging
from typing import List, Optional
import litellm

from dip.Config.config import config
from dip.research.schemas import ResearchRequest, ResearchResult, Evidence
from dip.research.retrieval.pipeline import RetrievalPipeline
from dip.research.retrieval.providers.duckduckgo import DuckDuckGoProvider
from dip.research.verification.pipeline import VerificationPipeline

logger = logging.getLogger("Research.Planner")

class ResearchPlanner:
    """Orchestrates autonomous web research."""
    
    def __init__(self):
        # In the future, this could be populated dynamically from a SourceRegistry
        self.providers = [DuckDuckGoProvider()]
        self.retrieval = RetrievalPipeline(self.providers)
        self.verification = VerificationPipeline()
        self.model = config.LLM_MODEL

    async def execute_from_gaps(self, missing_signals: List[str], country: str, query_context: str) -> ResearchResult:
        """
        Execute research specifically to fill missing evidence gaps (used by CRAG).
        """
        start_time = time.time()
        req = ResearchRequest(
            id=str(uuid.uuid4()),
            topic=query_context,
            queries=missing_signals,  # We just use the signals directly as initial queries
            countries=[country],
            news_only=False,
            max_results=3  # CRAG needs fast, targeted results
        )
        
        logger.info(f"Starting research for {len(missing_signals)} gaps...")
        
        # 1. Retrieve raw documents
        documents = await self.retrieval.retrieve(req)
        
        # 2. Verify into Evidence
        evidence = await self.verification.verify(documents, query_context=query_context)
        
        elapsed = time.time() - start_time
        logger.info(f"Research complete in {elapsed:.1f}s. Extracted {len(evidence)} verified findings.")
        
        # Build Result
        return ResearchResult(
            documents=documents,
            evidence=evidence,
            execution_time=elapsed,
            sources_used=[p.name for p in self.providers]
        )
