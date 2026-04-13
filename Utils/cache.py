"""
Redis Caching Layer for IND-Diplomat
Provides semantic caching with TTL for retrieval and LLM responses.
"""

import hashlib
import json
import os
from typing import Any, Optional, List, Dict
from datetime import timedelta

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("[Cache] Warning: redis package not installed. Caching disabled.")


class CacheService:
    """
    Production-grade caching service with:
    1. Semantic key generation
    2. TTL-based expiration
    3. Cache hit/miss metrics
    4. Graceful fallback when Redis unavailable
    """
    
    def __init__(self):
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        self.redis_password = os.getenv("REDIS_PASSWORD", None)
        
        self.default_ttl = int(os.getenv("CACHE_TTL_SECONDS", "3600"))  # 1 hour
        self.prefix = "ind_diplomat:"
        
        self._client = None
        self._connected = False
        self._stats = {"hits": 0, "misses": 0}
        
        self._connect()
    
    def _connect(self):
        """Attempts to connect to Redis."""
        if not REDIS_AVAILABLE:
            return
        
        try:
            self._client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Test connection
            self._client.ping()
            self._connected = True
            print(f"[Cache] Connected to Redis at {self.redis_host}:{self.redis_port}")
        except Exception as e:
            print(f"[Cache] Warning: Could not connect to Redis: {e}")
            self._connected = False
    
    def is_connected(self) -> bool:
        return self._connected
    
    def _generate_key(self, prefix: str, *args) -> str:
        """Generates a cache key from prefix and arguments."""
        # Create deterministic hash from arguments
        content = json.dumps(args, sort_keys=True)
        hash_value = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{self.prefix}{prefix}:{hash_value}"
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieves value from cache."""
        if not self._connected:
            return None
        
        try:
            value = self._client.get(key)
            if value:
                self._stats["hits"] += 1
                return json.loads(value)
            self._stats["misses"] += 1
            return None
        except Exception as e:
            print(f"[Cache] Get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Stores value in cache with TTL."""
        if not self._connected:
            return False
        
        try:
            serialized = json.dumps(value)
            self._client.setex(
                key,
                ttl or self.default_ttl,
                serialized
            )
            return True
        except Exception as e:
            print(f"[Cache] Set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Deletes a key from cache."""
        if not self._connected:
            return False
        
        try:
            self._client.delete(key)
            return True
        except Exception as e:
            print(f"[Cache] Delete error: {e}")
            return False
    
    def clear_prefix(self, prefix: str) -> int:
        """Clears all keys matching a prefix."""
        if not self._connected:
            return 0
        
        try:
            pattern = f"{self.prefix}{prefix}:*"
            keys = self._client.keys(pattern)
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            print(f"[Cache] Clear error: {e}")
            return 0
    
    # High-level caching methods
    
    def cache_retrieval(self, query: str, results: List[Dict], ttl: int = 1800) -> bool:
        """Caches retrieval results (30 min default TTL)."""
        key = self._generate_key("retrieval", query)
        return self.set(key, results, ttl)
    
    def get_cached_retrieval(self, query: str) -> Optional[List[Dict]]:
        """Gets cached retrieval results."""
        key = self._generate_key("retrieval", query)
        return self.get(key)
    
    def cache_llm_response(self, prompt: str, response: str, ttl: int = 3600) -> bool:
        """Caches LLM response (1 hour default TTL)."""
        key = self._generate_key("llm", prompt)
        return self.set(key, {"response": response}, ttl)
    
    def get_cached_llm_response(self, prompt: str) -> Optional[str]:
        """Gets cached LLM response."""
        key = self._generate_key("llm", prompt)
        cached = self.get(key)
        if cached:
            return cached.get("response")
        return None
    
    def cache_query_result(self, query: str, result: Dict, ttl: int = 1800) -> bool:
        """Caches full query result (30 min default TTL)."""
        key = self._generate_key("query", query)
        return self.set(key, result, ttl)
    
    def get_cached_query_result(self, query: str) -> Optional[Dict]:
        """Gets cached query result."""
        key = self._generate_key("query", query)
        return self.get(key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Returns cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0
        
        return {
            "connected": self._connected,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": round(hit_rate, 3),
            "host": f"{self.redis_host}:{self.redis_port}"
        }


# Singleton instance
cache = CacheService()
