"""
Politiq AI — Research Cache
===========================

Provides URL-based caching so we don't fetch/extract the same article twice.
"""

import hashlib
import json
import logging
from typing import Optional, Dict

logger = logging.getLogger("Research.Cache")


class URLCache:
    """Simple dictionary-backed cache for URLs (could be replaced with Redis/SQLite)."""
    
    def __init__(self):
        self._cache: Dict[str, str] = {}

    def _hash_url(self, url: str) -> str:
        return hashlib.sha256(url.encode('utf-8')).hexdigest()

    def get(self, url: str) -> Optional[str]:
        """Retrieve cached JSON string for a URL."""
        return self._cache.get(self._hash_url(url))

    def set(self, url: str, data: str):
        """Store JSON string for a URL."""
        self._cache[self._hash_url(url)] = data
