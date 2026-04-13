"""
Structured Tracing for IND-Diplomat
Provides detailed logging hooks for debugging ingestion, retrieval, and executor paths.
"""

import os
import json
import time
import uuid
import logging
import functools
from typing import Any, Dict, Optional, Callable
from contextlib import contextmanager
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False


class TracePhase(Enum):
    """Trace phases for the pipeline."""
    INGESTION = "ingestion"
    RETRIEVAL = "retrieval"
    REASONING = "reasoning"
    VERIFICATION = "verification"
    RESPONSE = "response"


@dataclass
class TraceSpan:
    """Represents a trace span."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation: str
    phase: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "in_progress"
    tags: Dict[str, Any] = None
    logs: list = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


class TracingContext:
    """Thread-local tracing context."""
    _current_trace_id: str = None
    _current_span_id: str = None
    _spans: Dict[str, TraceSpan] = {}
    
    @classmethod
    def new_trace(cls) -> str:
        cls._current_trace_id = str(uuid.uuid4())
        cls._current_span_id = None
        cls._spans = {}
        return cls._current_trace_id
    
    @classmethod
    def get_trace_id(cls) -> Optional[str]:
        return cls._current_trace_id
    
    @classmethod
    def get_span_id(cls) -> Optional[str]:
        return cls._current_span_id
    
    @classmethod
    def set_span(cls, span_id: str):
        cls._current_span_id = span_id


class Tracer:
    """
    Production-grade tracer with:
    1. Structured logging integration
    2. Span-based tracing
    3. Phase-aware logging
    4. Performance metrics
    """
    
    def __init__(self):
        self.enabled = os.getenv("TRACING_ENABLED", "true").lower() == "true"
        self.log_level = os.getenv("TRACE_LOG_LEVEL", "INFO")
        self.output_file = os.getenv("TRACE_OUTPUT_FILE", "./logs/traces.jsonl")
        
        # Setup logger
        if STRUCTLOG_AVAILABLE:
            structlog.configure(
                processors=[
                    structlog.stdlib.add_log_level,
                    structlog.stdlib.PositionalArgumentsFormatter(),
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.JSONRenderer()
                ],
                wrapper_class=structlog.stdlib.BoundLogger,
                context_class=dict,
                logger_factory=structlog.stdlib.LoggerFactory(),
            )
            self._logger = structlog.get_logger("ind_diplomat.tracer")
        else:
            logging.basicConfig(
                level=getattr(logging, self.log_level),
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            self._logger = logging.getLogger("ind_diplomat.tracer")
        
        # Ensure log directory exists
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
    
    def _write_trace(self, span: TraceSpan):
        """Writes trace to file."""
        if not self.enabled:
            return
        
        try:
            with open(self.output_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(span.to_dict()) + '\n')
        except Exception as e:
            self._logger.warning(f"Failed to write trace: {e}")
    
    @contextmanager
    def span(self, operation: str, phase: TracePhase, tags: Dict[str, Any] = None):
        """Creates a trace span context manager."""
        if not self.enabled:
            yield {}
            return
        
        trace_id = TracingContext.get_trace_id() or TracingContext.new_trace()
        parent_span_id = TracingContext.get_span_id()
        span_id = str(uuid.uuid4())[:8]
        
        span = TraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation=operation,
            phase=phase.value,
            start_time=time.time(),
            tags=tags or {},
            logs=[]
        )
        
        TracingContext.set_span(span_id)
        TracingContext._spans[span_id] = span
        
        self._logger.info(f"[{phase.value}] START {operation}", extra={
            "trace_id": trace_id,
            "span_id": span_id,
            "tags": tags
        })
        
        try:
            yield span
            span.status = "success"
        except Exception as e:
            span.status = "error"
            span.error = str(e)
            self._logger.error(f"[{phase.value}] ERROR {operation}: {e}", extra={
                "trace_id": trace_id,
                "span_id": span_id
            })
            raise
        finally:
            span.end_time = time.time()
            span.duration_ms = (span.end_time - span.start_time) * 1000
            
            self._logger.info(f"[{phase.value}] END {operation} ({span.duration_ms:.2f}ms)", extra={
                "trace_id": trace_id,
                "span_id": span_id,
                "duration_ms": span.duration_ms,
                "status": span.status
            })
            
            self._write_trace(span)
            TracingContext.set_span(parent_span_id)
    
    def log_event(self, message: str, phase: TracePhase = None, **kwargs):
        """Logs an event within current trace."""
        if not self.enabled:
            return
        
        trace_id = TracingContext.get_trace_id()
        span_id = TracingContext.get_span_id()
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "trace_id": trace_id,
            "span_id": span_id,
            "phase": phase.value if phase else None,
            "message": message,
            **kwargs
        }
        
        self._logger.info(message, extra=log_entry)
        
        # Add to current span logs
        if span_id and span_id in TracingContext._spans:
            TracingContext._spans[span_id].logs.append(log_entry)
    
    def trace_function(self, phase: TracePhase):
        """Decorator to trace a function."""
        def decorator(func: Callable):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                with self.span(func.__name__, phase, {"args_count": len(args)}):
                    return await func(*args, **kwargs)
            
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self.span(func.__name__, phase, {"args_count": len(args)}):
                    return func(*args, **kwargs)
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper
        return decorator


# Import asyncio for decorator
import asyncio

# Singleton instance
tracer = Tracer()


# Convenience functions
def trace_ingestion(operation: str, **tags):
    return tracer.span(operation, TracePhase.INGESTION, tags)

def trace_retrieval(operation: str, **tags):
    return tracer.span(operation, TracePhase.RETRIEVAL, tags)

def trace_reasoning(operation: str, **tags):
    return tracer.span(operation, TracePhase.REASONING, tags)

def trace_verification(operation: str, **tags):
    return tracer.span(operation, TracePhase.VERIFICATION, tags)

def log_event(message: str, phase: TracePhase = None, **kwargs):
    tracer.log_event(message, phase, **kwargs)
