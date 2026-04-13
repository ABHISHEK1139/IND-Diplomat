"""
Prometheus Metrics for IND-Diplomat
Provides observability and monitoring endpoints.
"""

import time
from typing import Dict, Any, Callable
from functools import wraps

try:
    from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    print("[Metrics] Warning: prometheus_client not installed. Metrics disabled.")


class MetricsCollector:
    """
    Production-grade metrics collector with:
    1. Request counters
    2. Latency histograms
    3. Cache statistics
    4. LLM usage tracking
    """
    
    def __init__(self):
        if not PROMETHEUS_AVAILABLE:
            self._enabled = False
            return
        
        self._enabled = True
        
        # Request metrics
        self.requests_total = Counter(
            'ind_diplomat_requests_total',
            'Total number of requests',
            ['endpoint', 'method', 'status']
        )
        
        self.request_latency = Histogram(
            'ind_diplomat_request_latency_seconds',
            'Request latency in seconds',
            ['endpoint'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
        )
        
        # LLM metrics
        self.llm_requests_total = Counter(
            'ind_diplomat_llm_requests_total',
            'Total LLM API calls',
            ['model', 'status']
        )
        
        self.llm_tokens_total = Counter(
            'ind_diplomat_llm_tokens_total',
            'Total tokens processed',
            ['model', 'type']  # type: input/output
        )
        
        self.llm_latency = Histogram(
            'ind_diplomat_llm_latency_seconds',
            'LLM call latency',
            ['model'],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
        )
        
        # Cache metrics
        self.cache_hits = Counter(
            'ind_diplomat_cache_hits_total',
            'Cache hits',
            ['cache_type']
        )
        
        self.cache_misses = Counter(
            'ind_diplomat_cache_misses_total',
            'Cache misses',
            ['cache_type']
        )
        
        # Retrieval metrics
        self.retrieval_latency = Histogram(
            'ind_diplomat_retrieval_latency_seconds',
            'Retrieval latency',
            ['source'],  # vector, graph, hybrid
            buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0]
        )
        
        self.retrieval_results = Histogram(
            'ind_diplomat_retrieval_results_count',
            'Number of results returned',
            ['source'],
            buckets=[0, 1, 5, 10, 20, 50]
        )
        
        # Verification metrics
        self.faithfulness_score = Histogram(
            'ind_diplomat_faithfulness_score',
            'Faithfulness scores distribution',
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        )
        
        self.verification_failures = Counter(
            'ind_diplomat_verification_failures_total',
            'Count of verification failures',
            ['reason']
        )
        
        # System metrics
        self.active_sessions = Gauge(
            'ind_diplomat_active_sessions',
            'Number of active sessions'
        )
        
        self.system_info = Info(
            'ind_diplomat_build',
            'Build information'
        )
        self.system_info.info({
            'version': '3.0.0',
            'service': 'ind-diplomat'
        })
    
    def is_enabled(self) -> bool:
        return self._enabled
    
    # Recording methods
    
    def record_request(self, endpoint: str, method: str, status: int, latency: float):
        """Records an API request."""
        if not self._enabled:
            return
        
        self.requests_total.labels(endpoint=endpoint, method=method, status=str(status)).inc()
        self.request_latency.labels(endpoint=endpoint).observe(latency)
    
    def record_llm_call(self, model: str, status: str, latency: float, input_tokens: int = 0, output_tokens: int = 0):
        """Records an LLM API call."""
        if not self._enabled:
            return
        
        self.llm_requests_total.labels(model=model, status=status).inc()
        self.llm_latency.labels(model=model).observe(latency)
        
        if input_tokens > 0:
            self.llm_tokens_total.labels(model=model, type="input").inc(input_tokens)
        if output_tokens > 0:
            self.llm_tokens_total.labels(model=model, type="output").inc(output_tokens)
    
    def record_cache_access(self, cache_type: str, hit: bool):
        """Records a cache access."""
        if not self._enabled:
            return
        
        if hit:
            self.cache_hits.labels(cache_type=cache_type).inc()
        else:
            self.cache_misses.labels(cache_type=cache_type).inc()
    
    def record_retrieval(self, source: str, latency: float, result_count: int):
        """Records a retrieval operation."""
        if not self._enabled:
            return
        
        self.retrieval_latency.labels(source=source).observe(latency)
        self.retrieval_results.labels(source=source).observe(result_count)
    
    def record_faithfulness(self, score: float):
        """Records a faithfulness score."""
        if not self._enabled:
            return
        
        self.faithfulness_score.observe(score)
    
    def record_verification_failure(self, reason: str):
        """Records a verification failure."""
        if not self._enabled:
            return
        
        self.verification_failures.labels(reason=reason).inc()
    
    def set_active_sessions(self, count: int):
        """Sets the active session count."""
        if not self._enabled:
            return
        
        self.active_sessions.set(count)
    
    def get_metrics(self) -> bytes:
        """Returns metrics in Prometheus format."""
        if not self._enabled:
            return b"# Metrics disabled\n"
        
        return generate_latest()
    
    def get_content_type(self) -> str:
        """Returns the content type for metrics response."""
        if not self._enabled:
            return "text/plain"
        return CONTENT_TYPE_LATEST


def timed_metric(collector: MetricsCollector, endpoint: str):
    """Decorator to automatically record request metrics."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            status = 200
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = 500
                raise
            finally:
                latency = time.perf_counter() - start_time
                collector.record_request(endpoint, "POST", status, latency)
        
        return wrapper
    return decorator


# Singleton instance
metrics = MetricsCollector()
