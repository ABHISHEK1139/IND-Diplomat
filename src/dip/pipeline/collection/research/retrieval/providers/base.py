"""
Politiq AI — Base Search Provider
=================================

Abstract base class for all search engines (DuckDuckGo, SearXNG, Brave, etc.)
"""

from abc import ABC, abstractmethod
from typing import List
from dip.pipeline.collection.research.schemas import SearchResult, ResearchRequest

class SearchProvider(ABC):
    """Abstract interface for all web search providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider (e.g., 'DuckDuckGo', 'SearXNG')."""
        pass

    @abstractmethod
    async def search(self, query: str, request: ResearchRequest) -> List[SearchResult]:
        """
        Execute a single search query and return a list of SearchResults.
        
        Args:
            query: The text string to search for.
            request: The full ResearchRequest (contains max_results, date_range, etc.).
            
        Returns:
            List of SearchResult objects containing title, url, and snippet.
        """
        pass
