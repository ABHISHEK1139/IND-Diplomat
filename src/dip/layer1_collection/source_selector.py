"""
Source Selector — Reranker Integration
========================================

Uses a CrossEncoder (e.g., BGE Reranker) to score and rank available
sources based on their relevance to the investigation objective.
"""

import logging
from typing import List

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None

from dip.core.schema import Investigation
from dip.layer1_collection.source_registry import SourceRegistry, SourceEntry

logger = logging.getLogger("Layer1.SourceSelector")


class SourceSelector:
    """
    Selects and ranks data sources using a cross-encoder (reranker)
    to match the investigation's objective to the source's description/domains.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.registry = SourceRegistry()
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if not CrossEncoder:
            logger.warning("sentence-transformers not installed. Using rule-based ranking.")
            return

        if self._model is None:
            logger.info(f"Loading CrossEncoder: {self.model_name}")
            try:
                self._model = CrossEncoder(self.model_name)
            except Exception as e:
                logger.error(f"Failed to load CrossEncoder: {e}")
                self._model = None

    def select(self, investigation: Investigation) -> List[SourceEntry]:
        """
        Rank all available sources against the investigation objective.
        Returns the top sources.
        """
        all_sources = self.registry.get_all()
        objective_text = investigation.objective.objective if investigation.objective else investigation.title
        
        self._load_model()
        
        if self._model is None:
            # Fallback to domain-based
            return self._fallback_select(investigation)

        # Build pairs of (Objective, Source Description)
        pairs = []
        for src in all_sources:
            desc = f"{src.name}. Covers: {', '.join(src.domains)}."
            pairs.append((objective_text, desc))
            
        try:
            # Score all pairs
            scores = self._model.predict(pairs)
            
            # Attach scores to sources
            scored_sources = list(zip(all_sources, scores))
            
            # Sort by score descending
            scored_sources.sort(key=lambda x: x[1], reverse=True)
            
            # Pick top 10 relevant sources (or those above a threshold)
            top_sources = [src for src, score in scored_sources[:10]]
            
            # Always ensure basic news is included
            ensure_ids = {"google_news", "gdelt"}
            for sid in ensure_ids:
                if not any(s.source_id == sid for s in top_sources):
                    top_sources.append(self.registry.get_source(sid))
                    
            logger.info(f"Reranker selected {len(top_sources)} sources.")
            return top_sources
            
        except Exception as e:
            logger.error(f"Reranker failed: {e}. Falling back.")
            return self._fallback_select(investigation)

    def _fallback_select(self, investigation: Investigation) -> List[SourceEntry]:
        """Original domain-based selection."""
        domains = list(investigation.scope.domains) if investigation.scope and investigation.scope.domains else ["General"]
        
        if investigation.scope and investigation.scope.countries:
            domains.extend(investigation.scope.countries)
            
        if investigation.collection_plan and investigation.collection_plan.needs:
            domains.extend([need.source_type for need in investigation.collection_plan.needs])

        sources = self.registry.get_sources_for_domains(domains)
        selected = {s.source_id: s for s in sources}
        
        selected["google_news"] = self.registry.get_source("google_news")
        selected["gdelt"] = self.registry.get_source("gdelt")
        
        return list(selected.values())
