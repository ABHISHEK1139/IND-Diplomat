
import logging
import json
import uuid
import time
from datetime import datetime
from typing import Optional
from functools import wraps

class StructuredLogger:
    """
    Production-grade Structured Logger with:
    1. JSON-formatted logs
    2. Correlation ID tracking
    3. Latency measurement
    """
    
    def __init__(self, name: str = "IND-Diplomat"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Avoid duplicate handlers
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(self.JsonFormatter())
            self.logger.addHandler(handler)
        
        self._correlation_id: Optional[str] = None
    
    class JsonFormatter(logging.Formatter):
        """Custom formatter that outputs JSON."""
        def format(self, record):
            log_record = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "module": record.module,
                "message": record.getMessage(),
            }
            
            # Add extra fields if present
            if hasattr(record, "correlation_id"):
                log_record["correlation_id"] = record.correlation_id
            if hasattr(record, "latency_ms"):
                log_record["latency_ms"] = record.latency_ms
            if hasattr(record, "extra_data"):
                log_record["data"] = record.extra_data
            
            return json.dumps(log_record)
    
    def set_correlation_id(self, correlation_id: str = None):
        """Sets correlation ID for request tracing."""
        self._correlation_id = correlation_id or str(uuid.uuid4())
        return self._correlation_id
    
    def get_correlation_id(self) -> str:
        """Gets current correlation ID."""
        return self._correlation_id or "no-correlation-id"
    
    def _log(self, level: str, message: str, extra_data: dict = None, latency_ms: float = None):
        """Internal logging method."""
        extra = {
            "correlation_id": self.get_correlation_id(),
        }
        if extra_data:
            extra["extra_data"] = extra_data
        if latency_ms is not None:
            extra["latency_ms"] = round(latency_ms, 2)
        
        log_method = getattr(self.logger, level.lower())
        log_method(message, extra=extra)
    
    def info(self, message: str, **kwargs):
        self._log("info", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log("warning", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log("error", message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        self._log("debug", message, **kwargs)


def timed_operation(logger: StructuredLogger, operation_name: str):
    """Decorator to measure and log operation latency."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                latency = (time.perf_counter() - start) * 1000
                logger.info(f"{operation_name} completed", latency_ms=latency)
                return result
            except Exception as e:
                latency = (time.perf_counter() - start) * 1000
                logger.error(f"{operation_name} failed: {e}", latency_ms=latency)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                latency = (time.perf_counter() - start) * 1000
                logger.info(f"{operation_name} completed", latency_ms=latency)
                return result
            except Exception as e:
                latency = (time.perf_counter() - start) * 1000
                logger.error(f"{operation_name} failed: {e}", latency_ms=latency)
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


# Singleton logger instance
logger = StructuredLogger()
