"""
Politiq AI — Web Crawler
========================

Parallel asynchronous crawler to fetch HTML from multiple URLs efficiently.
"""

import asyncio
import logging
import aiohttp
from typing import List, Dict, Optional

logger = logging.getLogger("Research.Crawler")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 PolitiqAI/3.0"

class WebCrawler:
    """Fetches web pages in parallel using aiohttp."""
    
    def __init__(self, timeout_seconds: int = 15, max_concurrent: int = 10):
        self.timeout_seconds = timeout_seconds
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_url(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """Fetch a single URL with timeout and standard headers."""
        async with self.semaphore:
            try:
                headers = {"User-Agent": USER_AGENT}
                async with session.get(url, headers=headers, timeout=self.timeout_seconds) as response:
                    if response.status == 200:
                        content_type = response.headers.get("Content-Type", "")
                        if "text/html" in content_type or "text/plain" in content_type:
                            return await response.text()
                        else:
                            logger.warning(f"Skipping non-HTML content at {url}: {content_type}")
                            return None
                    else:
                        logger.warning(f"Failed to fetch {url}: HTTP {response.status}")
                        return None
            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching {url}")
                return None
            except Exception as e:
                logger.warning(f"Error fetching {url}: {e}")
                return None

    async def crawl(self, urls: List[str]) -> Dict[str, Optional[str]]:
        """
        Crawl multiple URLs in parallel.
        
        Args:
            urls: List of URLs to fetch.
            
        Returns:
            Dictionary mapping URL to its HTML content (or None if failed).
        """
        results: Dict[str, Optional[str]] = {}
        if not urls:
            return results

        # Create a single aiohttp session for connection pooling
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_url(session, url) for url in urls]
            html_contents = await asyncio.gather(*tasks, return_exceptions=True)
            
            for url, content in zip(urls, html_contents):
                if isinstance(content, Exception):
                    logger.warning(f"Gather error for {url}: {content}")
                    results[url] = None
                else:
                    results[url] = content
                    
        return results
