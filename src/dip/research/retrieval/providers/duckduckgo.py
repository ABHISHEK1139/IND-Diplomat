"""
Politiq AI — DuckDuckGo Provider
=================================

Implementation of the SearchProvider interface using duckduckgo_search.
"""

import asyncio
import logging
from typing import List
from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException

from dip.research.schemas import SearchResult, ResearchRequest
from dip.research.retrieval.providers.base import SearchProvider

logger = logging.getLogger("Research.DuckDuckGo")

class DuckDuckGoProvider(SearchProvider):
    """Search provider using the open DuckDuckGo API."""
    
    @property
    def name(self) -> str:
        return "DuckDuckGo"

    async def search(self, query: str, request: ResearchRequest) -> List[SearchResult]:
        results: List[SearchResult] = []
        max_res = request.max_results
        
        # Determine if we should use news search based on request
        use_news = request.news_only
        
        # Map date range to DDG format if possible
        # DDG supports d (day), w (week), m (month), y (year)
        timelimit = None
        if request.date_range:
            dr = request.date_range.lower()
            if "day" in dr or "24" in dr:
                timelimit = "d"
            elif "week" in dr:
                timelimit = "w"
            elif "month" in dr:
                timelimit = "m"
            elif "year" in dr:
                timelimit = "y"

        try:
            # duckduckgo_search is synchronous, so we run it in a thread pool
            loop = asyncio.get_event_loop()
            
            def _do_search():
                with DDGS() as ddgs:
                    if use_news:
                        return list(ddgs.news(query, max_results=max_res, timelimit=timelimit))
                    else:
                        return list(ddgs.text(query, max_results=max_res, timelimit=timelimit))
            
            raw_results = await loop.run_in_executor(None, _do_search)
            
            for rank, r in enumerate(raw_results):
                # DDG text returns: title, href, body
                # DDG news returns: title, url, body, source, date
                
                title = r.get("title", "")
                url = r.get("href") or r.get("url", "")
                snippet = r.get("body", "")
                source = r.get("source", "DuckDuckGo")
                
                # We calculate a simple score based on rank (1.0 for first, decaying)
                score = max(0.1, 1.0 - (rank * 0.05))
                
                if url:
                    results.append(SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source=source,
                        score=score
                    ))
                    
        except DuckDuckGoSearchException as e:
            logger.error(f"DuckDuckGo search failed for query '{query}': {e}")
        except Exception as e:
            logger.error(f"Unexpected error in DuckDuckGo search: {e}")
            
        return results
