"""
Politiq AI — Retrieval Pipeline
===============================

Orchestrates the flow from Search -> Cache Check -> Parallel Crawl -> Extract -> Document.
"""

import asyncio
import json
import logging
from typing import List, Dict

from dip.pipeline.collection.research.schemas import ResearchRequest, SearchResult, Document
from dip.pipeline.collection.research.retrieval.providers.base import SearchProvider
from dip.pipeline.collection.research.retrieval.crawler import WebCrawler
from dip.pipeline.collection.research.retrieval.extractor import ContentExtractor
from dip.pipeline.collection.research.cache.simple_cache import URLCache

logger = logging.getLogger("Research.RetrievalPipeline")


class RetrievalPipeline:
    """End-to-end retrieval orchestrator."""
    
    def __init__(self, providers: List[SearchProvider]):
        self.providers = providers
        self.crawler = WebCrawler(timeout_seconds=15, max_concurrent=10)
        self.extractor = ContentExtractor()
        self.cache = URLCache()

    async def retrieve(self, request: ResearchRequest) -> List[Document]:
        """
        Execute the full retrieval pipeline.
        
        Args:
            request: The parameterized research request.
            
        Returns:
            List of extracted Document objects.
        """
        all_search_results: List[SearchResult] = []
        
        # 1. Search across all selected providers for all queries
        for provider in self.providers:
            if request.required_sources and provider.name.lower() not in [s.lower() for s in request.required_sources]:
                continue
            if provider.name.lower() in [s.lower() for s in request.excluded_sources]:
                continue
                
            for query in request.queries:
                logger.info(f"[{provider.name}] Searching: '{query}'")
                results = await provider.search(query, request)
                all_search_results.extend(results)
                
        # 2. Deduplicate URLs (pick the highest score if duplicate)
        unique_urls: Dict[str, SearchResult] = {}
        for r in all_search_results:
            if r.url not in unique_urls or r.score > unique_urls[r.url].score:
                unique_urls[r.url] = r
                
        logger.info(f"Found {len(unique_urls)} unique URLs from search.")
        
        final_documents: List[Document] = []
        urls_to_crawl: List[str] = []
        
        # 3. Check Cache
        for url, search_res in unique_urls.items():
            cached_doc_json = self.cache.get(url)
            if cached_doc_json:
                try:
                    doc = Document.model_validate_json(cached_doc_json)
                    final_documents.append(doc)
                    logger.debug(f"Cache hit for {url}")
                except Exception as e:
                    logger.warning(f"Failed to parse cached document for {url}: {e}")
                    urls_to_crawl.append(url)
            else:
                urls_to_crawl.append(url)
                
        logger.info(f"Cache hits: {len(final_documents)}. URLs to crawl: {len(urls_to_crawl)}")
        
        # 4. Crawl the remaining URLs in parallel
        if urls_to_crawl:
            crawled_data = await self.crawler.crawl(urls_to_crawl)
            
            # 5. Extract Content
            for url, html in crawled_data.items():
                if html:
                    base_title = unique_urls[url].title
                    doc = self.extractor.extract(url, html, base_title=base_title)
                    if doc:
                        final_documents.append(doc)
                        # Save to cache
                        self.cache.set(url, doc.model_dump_json())
                        
        logger.info(f"Retrieval complete. Successfully extracted {len(final_documents)} documents.")
        return final_documents
