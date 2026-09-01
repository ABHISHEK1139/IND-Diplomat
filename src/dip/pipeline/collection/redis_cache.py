"""
Redis Cache Layer — DIP 2.1

Provides application-level caching for:
  - Country state contexts (avoid rebuilding per query)
  - Sensor results (avoid re-fetching within TTL window)
  - Council deliberation results (cache identical queries)
  - Vector search results

With graceful degradation: if Redis is unavailable, falls back to
in-memory dict cache (no data loss, just no persistence).
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Optional

from dip.core.Config.config import config

try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


class RedisCache:
    """
    Redis-backed cache with in-memory fallback.
    
    Usage:
        cache = RedisCache(prefix="dip2")
        await cache.connect()
        await cache.set("key", value, ttl=300)
        value = await cache.get("key")
    """
    
    def __init__(
        self,
        prefix: str = "dip2",
        default_ttl: int = 300,
        url: Optional[str] = None,
    ):
        self.prefix = prefix
        self.default_ttl = default_ttl
        self.url = url or config.REDIS_URL
        self._redis = None
        self._fallback: Dict[str, tuple[Any, float]] = {}  # key → (value, expiry)
        self._connected = False
    
    async def connect(self) -> bool:
        """Connect to Redis. Returns True if Redis is available."""
        if not HAS_REDIS or not self.url:
            self._connected = False
            return False
        
        try:
            self._redis = await aioredis.from_url(
                self.url,
                decode_responses=False,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            await self._redis.ping()
            self._connected = True
            return True
        except Exception:
            self._redis = None
            self._connected = False
            return False
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
        self._connected = False
    
    def _make_key(self, key: str) -> str:
        return f"{self.prefix}:{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a cached value."""
        full_key = self._make_key(key)
        
        # Try Redis
        if self._redis and self._connected:
            try:
                raw = await self._redis.get(full_key)
                if raw:
                    return json.loads(raw)
            except Exception:
                pass
        
        # Fallback to in-memory
        if full_key in self._fallback:
            value, expiry = self._fallback[full_key]
            if time.time() < expiry:
                return value
            del self._fallback[full_key]
        
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a cached value with TTL in seconds."""
        full_key = self._make_key(key)
        ttl = ttl or self.default_ttl
        serialized = json.dumps(value, default=str)
        
        # Try Redis
        if self._redis and self._connected:
            try:
                await self._redis.setex(full_key, ttl, serialized)
                return
            except Exception:
                pass
        
        # Fallback to in-memory
        self._fallback[full_key] = (value, time.time() + ttl)
    
    async def delete(self, key: str) -> None:
        """Delete a cached key."""
        full_key = self._make_key(key)
        
        if self._redis and self._connected:
            try:
                await self._redis.delete(full_key)
            except Exception:
                pass
        
        self._fallback.pop(full_key, None)
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        full_key = self._make_key(key)
        
        if self._redis and self._connected:
            try:
                return bool(await self._redis.exists(full_key))
            except Exception:
                pass
        
        if full_key in self._fallback:
            _, expiry = self._fallback[full_key]
            if time.time() < expiry:
                return True
            del self._fallback[full_key]
        
        return False
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment a counter."""
        full_key = self._make_key(key)
        
        if self._redis and self._connected:
            try:
                return int(await self._redis.incrby(full_key, amount))
            except Exception:
                pass
        
        # Fallback
        current = self._fallback.get(full_key, (0, float("inf")))[0]
        new_val = int(current) + amount
        self._fallback[full_key] = (new_val, float("inf"))
        return new_val
    
    def cache_key(self, *parts: str) -> str:
        """Generate a deterministic cache key from parts."""
        joined = ":".join(str(p) for p in parts)
        return hashlib.sha256(joined.encode()).hexdigest()[:16]
    
    @property
    def connected(self) -> bool:
        return self._connected


# ── Domain-specific cache helpers ──

class StateContextCache:
    """Caches Layer 3 state contexts per country."""
    
    def __init__(self, redis_cache: Optional[RedisCache] = None):
        self.cache = redis_cache or RedisCache(prefix="dip2:state")
        self._default_ttl = 900  # 15 minutes
    
    async def get_state(self, country: str) -> Optional[Dict[str, Any]]:
        key = f"state:{country.upper()}"
        return await self.cache.get(key)
    
    async def set_state(self, country: str, state: Dict[str, Any]) -> None:
        key = f"state:{country.upper()}"
        await self.cache.set(key, state, ttl=self._default_ttl)
    
    async def invalidate(self, country: str) -> None:
        key = f"state:{country.upper()}"
        await self.cache.delete(key)


class SensorResultCache:
    """Caches sensor fetch results per country to avoid rate-limiting."""
    
    def __init__(self, redis_cache: Optional[RedisCache] = None):
        self.cache = redis_cache or RedisCache(prefix="dip2:sensor")
        self._default_ttl = 600  # 10 minutes
    
    async def get_results(self, country: str, sensor: str) -> Optional[list]:
        key = f"results:{country.upper()}:{sensor}"
        return await self.cache.get(key)
    
    async def set_results(self, country: str, sensor: str, results: list) -> None:
        key = f"results:{country.upper()}:{sensor}"
        await self.cache.set(key, results, ttl=self._default_ttl)


class AssessmentCache:
    """Caches pipeline results for identical queries."""
    
    def __init__(self, redis_cache: Optional[RedisCache] = None):
        self.cache = redis_cache or RedisCache(prefix="dip2:assessment")
        self._default_ttl = 1800  # 30 minutes
    
    async def get_assessment(self, query: str, country: str) -> Optional[Dict[str, Any]]:
        key = self.cache.cache_key(query, country)
        return await self.cache.get(key)
    
    async def set_assessment(self, query: str, country: str, result: Dict[str, Any]) -> None:
        key = self.cache.cache_key(query, country)
        await self.cache.set(key, result, ttl=self._default_ttl)


# ── Global cache instance ──
_global_cache: Optional[RedisCache] = None


async def get_cache() -> RedisCache:
    """Get or create the global Redis cache."""
    global _global_cache
    if _global_cache is None:
        _global_cache = RedisCache()
        connected = await _global_cache.connect()
        if connected:
            import logging
            logging.getLogger("dip2.cache").info("Redis cache connected")
        else:
            import logging
            logging.getLogger("dip2.cache").info("Using in-memory fallback cache")
    return _global_cache
