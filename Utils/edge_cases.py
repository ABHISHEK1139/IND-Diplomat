"""
Premium Edge Case Utilities
============================
Smart protection that doesn't constrain legitimate users.
All limits are designed for enterprise/diplomatic use cases.
"""

import time
import asyncio
from typing import Dict, Any, Optional, Callable, TypeVar
from dataclasses import dataclass, field
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================
# 1. SMART RATE LIMITING (Premium-tier generous limits)
# ============================================================

@dataclass
class RateLimitConfig:
    """Premium rate limit configuration."""
    # Very generous limits for premium service
    requests_per_minute: int = 120       # 2 requests/second
    requests_per_hour: int = 3000        # 50 requests/minute avg
    burst_allowance: int = 20            # Extra burst capacity
    
    # Special limits for heavy operations
    heavy_ops_per_minute: int = 30       # MCTS, Causal, etc.


@dataclass
class RateLimitResult:
    """Return type that supports both tuple unpacking and dict-style access."""
    allowed: bool
    remaining: int
    retry_after: float
    message: Optional[str]

    def __iter__(self):
        # Enables: allowed, retry_after = rate_limiter.check_limit(...)
        yield self.allowed
        yield self.retry_after

    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key: str):
        return getattr(self, key)


class SmartRateLimiter:
    """
    Token-bucket rate limiter with burst support.
    Designed to be invisible to normal users.
    """
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self._buckets: Dict[str, Dict] = {}
    
    def _get_bucket(self, key: str) -> Dict:
        now = time.time()
        if key not in self._buckets:
            self._buckets[key] = {
                "tokens": self.config.requests_per_minute + self.config.burst_allowance,
                "last_update": now,
                "hourly_count": 0,
                "hour_start": now
            }
        return self._buckets[key]
    
    def _refill_tokens(self, bucket: Dict):
        """Refill tokens based on time passed."""
        now = time.time()
        elapsed = now - bucket["last_update"]
        
        # Refill at rate of requests_per_minute / 60 per second
        refill_rate = self.config.requests_per_minute / 60.0
        tokens_to_add = elapsed * refill_rate
        
        max_tokens = self.config.requests_per_minute + self.config.burst_allowance
        bucket["tokens"] = min(max_tokens, bucket["tokens"] + tokens_to_add)
        bucket["last_update"] = now
        
        # Reset hourly counter if hour passed
        if now - bucket["hour_start"] > 3600:
            bucket["hourly_count"] = 0
            bucket["hour_start"] = now
    
    def check_limit(self, user_id: str = "default", is_heavy: bool = False) -> RateLimitResult:
        """
        Check if request is within limits.
        Returns: RateLimitResult (dict- and tuple-like for compatibility)
        """
        bucket = self._get_bucket(user_id)
        self._refill_tokens(bucket)
        
        # Check hourly limit
        if bucket["hourly_count"] >= self.config.requests_per_hour:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                retry_after=60,
                message="You've reached your hourly limit. Premium users get 3000 requests/hour.",
            )
        
        # Check tokens (per-minute with burst)
        required = 2.0 if is_heavy else 1.0
        if bucket["tokens"] < required:
            # Calculate wait time
            refill_rate = self.config.requests_per_minute / 60.0
            wait_seconds = (required - bucket["tokens"]) / refill_rate
            
            return RateLimitResult(
                allowed=False,
                remaining=int(bucket["tokens"]),
                retry_after=round(wait_seconds, 1),
                message=f"Please wait {wait_seconds:.1f}s. Processing previous request.",
            )
        
        # Allow request
        bucket["tokens"] -= required
        bucket["hourly_count"] += 1
        
        return RateLimitResult(
            allowed=True,
            remaining=int(bucket["tokens"]),
            retry_after=0,
            message=None,
        )
    
    def cleanup_old_buckets(self, max_age: int = 7200):
        """Clean up buckets older than max_age seconds."""
        now = time.time()
        to_remove = [k for k, v in self._buckets.items() if now - v["last_update"] > max_age]
        for key in to_remove:
            del self._buckets[key]


# Global rate limiter
rate_limiter = SmartRateLimiter()


# ============================================================
# 2. SMART TIMEOUT HANDLING (With retries)
# ============================================================

@dataclass
class TimeoutConfig:
    """Premium timeout configuration - generous but safe."""
    # LLM operations (can be slow)
    llm_timeout: float = 120.0           # 2 minutes for complex queries
    llm_retries: int = 2                 # Retry twice on timeout
    
    # Retrieval operations
    retrieval_timeout: float = 30.0      # 30s for search
    
    # External APIs
    external_timeout: float = 45.0       # 45s for WTO/UNCTAD
    
    # Graph database
    graph_timeout: float = 20.0          # 20s for Neo4j


class TimeoutHandler:
    """
    Smart timeout handler with exponential backoff retry.
    """
    
    def __init__(self, config: TimeoutConfig = None):
        self.config = config or TimeoutConfig()
    
    async def with_timeout(
        self,
        coro,
        timeout: float = None,
        retries: int = None,
        fallback: Any = None,
        operation_name: str = "operation"
    ) -> Any:
        """
        Execute coroutine with timeout and retry.
        
        Args:
            coro: Coroutine to execute
            timeout: Timeout in seconds
            retries: Number of retries
            fallback: Value to return on failure
            operation_name: Name for logging
        """
        timeout = timeout or self.config.llm_timeout
        retries = retries if retries is not None else self.config.llm_retries
        
        last_error = None
        
        for attempt in range(retries + 1):
            try:
                return await asyncio.wait_for(coro, timeout=timeout)
            except asyncio.TimeoutError:
                last_error = f"Timeout after {timeout}s"
                logger.warning(f"[{operation_name}] Attempt {attempt + 1}/{retries + 1}: {last_error}")
                
                if attempt < retries:
                    # Exponential backoff: 1s, 2s, 4s...
                    await asyncio.sleep(2 ** attempt)
                    # For retries, recreate the coroutine if it's a callable
                    if callable(coro):
                        coro = coro()
            except Exception as e:
                last_error = str(e)
                logger.error(f"[{operation_name}] Error: {last_error}")
                break
        
        if fallback is not None:
            return fallback
        
        raise TimeoutError(f"{operation_name} failed: {last_error}")


timeout_handler = TimeoutHandler()


# ============================================================
# 3. SMART INPUT VALIDATION (Generous limits)
# ============================================================

@dataclass
class ValidationConfig:
    """Premium validation limits - generous for enterprise use."""
    # Query limits - very generous for diplomatic documents
    max_query_length: int = 50000        # 50K chars (~10K words)
    min_query_length: int = 3            # At least 3 chars
    
    # Batch limits
    max_batch_size: int = 100            # 100 items per batch
    
    # File limits
    max_file_size_mb: int = 100          # 100MB files
    
    # Document limits
    max_context_documents: int = 50      # 50 docs in context


class InputValidator:
    """
    Smart input validation with helpful error messages.
    """
    
    def __init__(self, config: ValidationConfig = None):
        self.config = config or ValidationConfig()
    
    def validate_query(self, query: str) -> Dict[str, Any]:
        """
        Validate query with helpful feedback.
        Returns: {valid, query, truncated, message}
        """
        if not query or not query.strip():
            return {
                "valid": False,
                "query": None,
                "truncated": False,
                "message": "Please provide a query."
            }
        
        query = query.strip()
        
        if len(query) < self.config.min_query_length:
            return {
                "valid": False,
                "query": None,
                "truncated": False,
                "message": f"Query too short. Please provide more context."
            }
        
        # For extremely long queries, smart truncate with notice
        if len(query) > self.config.max_query_length:
            truncated_query = query[:self.config.max_query_length]
            # Find last sentence boundary
            for end_char in ['. ', '? ', '! ', '\n']:
                last_pos = truncated_query.rfind(end_char)
                if last_pos > self.config.max_query_length * 0.8:
                    truncated_query = truncated_query[:last_pos + 1]
                    break
            
            return {
                "valid": True,
                "query": truncated_query,
                "truncated": True,
                "message": f"Query truncated from {len(query)} to {len(truncated_query)} characters for optimal processing."
            }
        
        return {
            "valid": True,
            "query": query,
            "truncated": False,
            "message": None
        }
    
    def sanitize_input(self, text: str) -> str:
        """Sanitize input while preserving diplomatic content."""
        if not text:
            return ""
        
        # Remove null bytes and control chars (but keep newlines, tabs)
        sanitized = ''.join(c for c in text if c == '\n' or c == '\t' or (ord(c) >= 32))
        
        return sanitized


input_validator = InputValidator()


# ============================================================
# 4. SMART MEMORY LIMITS (Pagination, not hard cuts)
# ============================================================

@dataclass
class MemoryConfig:
    """Memory management configuration."""
    # Document limits
    max_documents_per_query: int = 50    # Max docs in single response
    default_page_size: int = 20          # Default pagination
    max_page_size: int = 100             # Max single page
    
    # Content limits
    max_content_per_doc_kb: int = 100    # 100KB per doc content
    max_total_content_kb: int = 2000     # 2MB total content


class MemoryManager:
    """
    Smart memory management with pagination.
    """
    
    def __init__(self, config: MemoryConfig = None):
        self.config = config or MemoryConfig()
    
    def paginate_results(
        self,
        results: list,
        page: int = 1,
        page_size: int = None
    ) -> Dict[str, Any]:
        """
        Paginate results with metadata.
        """
        page_size = min(page_size or self.config.default_page_size, self.config.max_page_size)
        total_count = len(results)
        total_pages = (total_count + page_size - 1) // page_size
        
        page = max(1, min(page, total_pages or 1))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        return {
            "data": results[start_idx:end_idx],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    
    def limit_documents(
        self,
        documents: list,
        max_count: int = None
    ) -> Dict[str, Any]:
        """
        Limit documents with notification.
        """
        max_count = max_count or self.config.max_documents_per_query
        
        if len(documents) <= max_count:
            return {
                "documents": documents,
                "limited": False,
                "total_available": len(documents),
                "returned": len(documents)
            }
        
        return {
            "documents": documents[:max_count],
            "limited": True,
            "total_available": len(documents),
            "returned": max_count,
            "message": f"Showing top {max_count} of {len(documents)} results. Request more via pagination."
        }
    
    def truncate_content(
        self,
        content: str,
        max_kb: int = None
    ) -> Dict[str, Any]:
        """
        Smart content truncation at natural boundaries.
        """
        max_kb = max_kb or self.config.max_content_per_doc_kb
        max_chars = max_kb * 1024
        
        if len(content) <= max_chars:
            return {"content": content, "truncated": False}
        
        # Truncate at paragraph boundary
        truncated = content[:max_chars]
        last_para = truncated.rfind('\n\n')
        if last_para > max_chars * 0.7:
            truncated = truncated[:last_para]
        
        return {
            "content": truncated + "\n\n[Content truncated for optimal processing]",
            "truncated": True,
            "original_size_kb": len(content) // 1024,
            "truncated_size_kb": len(truncated) // 1024
        }


memory_manager = MemoryManager()


# ============================================================
# CONVENIENCE DECORATORS
# ============================================================

def rate_limited(user_id_param: str = "user_id", is_heavy: bool = False):
    """Decorator for rate limiting endpoints."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_id = kwargs.get(user_id_param, "default")
            check = rate_limiter.check_limit(user_id, is_heavy=is_heavy)
            
            if not check.allowed:
                raise Exception(f"Rate limit exceeded: {check.message}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def with_timeout(timeout: float = 60.0, fallback: Any = None):
    """Decorator for timeout handling."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await timeout_handler.with_timeout(
                func(*args, **kwargs),
                timeout=timeout,
                fallback=fallback,
                operation_name=func.__name__
            )
        return wrapper
    return decorator


def validated_input(param_name: str = "query"):
    """Decorator for input validation."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if param_name in kwargs:
                result = input_validator.validate_query(kwargs[param_name])
                if not result["valid"]:
                    raise ValueError(result["message"])
                kwargs[param_name] = result["query"]
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Export all
__all__ = [
    'rate_limiter', 'SmartRateLimiter', 'RateLimitConfig',
    'timeout_handler', 'TimeoutHandler', 'TimeoutConfig',
    'input_validator', 'InputValidator', 'ValidationConfig',
    'memory_manager', 'MemoryManager', 'MemoryConfig',
    'rate_limited', 'with_timeout', 'validated_input'
]
