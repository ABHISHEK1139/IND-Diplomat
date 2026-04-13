"""
Industrial Observability and Distributed Tracing
Integrates LangSmith/Arize Phoenix style trace logging for RAG pipeline debugging.
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from contextlib import contextmanager
import uuid
import time
import json
import threading


class TraceType(Enum):
    """Types of traced operations."""
    QUERY = "query"
    RETRIEVAL = "retrieval"
    RERANK = "rerank"
    GENERATION = "generation"
    VERIFICATION = "verification"
    TOOL_CALL = "tool_call"
    AGENT_STEP = "agent_step"
    MEMORY_ACCESS = "memory_access"


class TraceStatus(Enum):
    """Status of a trace span."""
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class TraceSpan:
    """A single span in the trace."""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    operation_name: str
    trace_type: TraceType
    status: TraceStatus
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[float]
    
    # Input/Output
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    error: Optional[str] = None
    
    # Metrics
    token_count: Optional[int] = None
    retrieval_count: Optional[int] = None
    confidence_score: Optional[float] = None


@dataclass  
class Trace:
    """A complete trace of a RAG execution."""
    trace_id: str
    session_id: str
    user_id: Optional[str]
    query: str
    start_time: datetime
    end_time: Optional[datetime]
    status: TraceStatus
    spans: List[TraceSpan]
    
    # Aggregated metrics
    total_duration_ms: Optional[float] = None
    total_tokens: int = 0
    total_retrievals: int = 0
    final_confidence: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary for export."""
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "query": self.query,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status.value,
            "total_duration_ms": self.total_duration_ms,
            "total_tokens": self.total_tokens,
            "total_retrievals": self.total_retrievals,
            "final_confidence": self.final_confidence,
            "spans": [
                {
                    "span_id": s.span_id,
                    "parent_span_id": s.parent_span_id,
                    "operation_name": s.operation_name,
                    "trace_type": s.trace_type.value,
                    "status": s.status.value,
                    "duration_ms": s.duration_ms,
                    "error": s.error,
                    "confidence_score": s.confidence_score
                }
                for s in self.spans
            ]
        }


class ObservabilityManager:
    """
    Manages distributed tracing for the RAG pipeline.
    Enables replay and debugging of reasoning chains.
    """
    
    def __init__(self, export_endpoint: str = None):
        self._traces: Dict[str, Trace] = {}
        self._active_spans: Dict[str, TraceSpan] = {}
        self._export_endpoint = export_endpoint
        self._lock = threading.Lock()
        
        # Thread-local storage for current context
        self._context = threading.local()
    
    def start_trace(
        self,
        query: str,
        session_id: str = None,
        user_id: str = None
    ) -> str:
        """Start a new trace for a query."""
        trace_id = str(uuid.uuid4())
        
        trace = Trace(
            trace_id=trace_id,
            session_id=session_id or str(uuid.uuid4()),
            user_id=user_id,
            query=query,
            start_time=datetime.now(),
            end_time=None,
            status=TraceStatus.STARTED,
            spans=[]
        )
        
        with self._lock:
            self._traces[trace_id] = trace
        
        self._context.trace_id = trace_id
        self._context.span_stack = []
        
        return trace_id
    
    def end_trace(
        self,
        trace_id: str,
        status: TraceStatus = TraceStatus.COMPLETED,
        final_confidence: float = None
    ):
        """End an active trace."""
        with self._lock:
            if trace_id not in self._traces:
                return
            
            trace = self._traces[trace_id]
            trace.end_time = datetime.now()
            trace.status = status
            trace.final_confidence = final_confidence
            
            # Calculate total duration
            trace.total_duration_ms = (trace.end_time - trace.start_time).total_seconds() * 1000
            
            # Aggregate metrics from spans
            for span in trace.spans:
                if span.token_count:
                    trace.total_tokens += span.token_count
                if span.retrieval_count:
                    trace.total_retrievals += span.retrieval_count
        
        # Export trace
        if self._export_endpoint:
            self._export_trace(trace)
    
    def start_span(
        self,
        operation_name: str,
        trace_type: TraceType,
        input_data: Dict[str, Any] = None,
        parent_span_id: str = None,
        tags: List[str] = None
    ) -> str:
        """Start a new span within the current trace."""
        trace_id = getattr(self._context, 'trace_id', None)
        if not trace_id:
            return None
        
        span_id = str(uuid.uuid4())
        
        # Get parent from stack if not provided
        if parent_span_id is None:
            span_stack = getattr(self._context, 'span_stack', [])
            parent_span_id = span_stack[-1] if span_stack else None
        
        span = TraceSpan(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            trace_type=trace_type,
            status=TraceStatus.STARTED,
            start_time=datetime.now(),
            end_time=None,
            duration_ms=None,
            input_data=input_data or {},
            output_data=None,
            tags=tags or []
        )
        
        with self._lock:
            self._active_spans[span_id] = span
            if trace_id in self._traces:
                self._traces[trace_id].spans.append(span)
        
        # Push to stack
        if hasattr(self._context, 'span_stack'):
            self._context.span_stack.append(span_id)
        
        return span_id
    
    def end_span(
        self,
        span_id: str,
        output_data: Dict[str, Any] = None,
        status: TraceStatus = TraceStatus.COMPLETED,
        error: str = None,
        token_count: int = None,
        retrieval_count: int = None,
        confidence_score: float = None
    ):
        """End an active span."""
        with self._lock:
            if span_id not in self._active_spans:
                return
            
            span = self._active_spans[span_id]
            span.end_time = datetime.now()
            span.status = status
            span.output_data = output_data
            span.error = error
            span.token_count = token_count
            span.retrieval_count = retrieval_count
            span.confidence_score = confidence_score
            span.duration_ms = (span.end_time - span.start_time).total_seconds() * 1000
            
            del self._active_spans[span_id]
        
        # Pop from stack
        if hasattr(self._context, 'span_stack') and span_id in self._context.span_stack:
            self._context.span_stack.remove(span_id)
    
    @contextmanager
    def trace_operation(
        self,
        operation_name: str,
        trace_type: TraceType,
        input_data: Dict[str, Any] = None,
        tags: List[str] = None
    ):
        """Context manager for tracing an operation."""
        span_id = self.start_span(operation_name, trace_type, input_data, tags=tags)
        
        try:
            result = {"output": None, "error": None}
            yield result
            self.end_span(span_id, output_data=result.get("output"))
        except Exception as e:
            self.end_span(span_id, status=TraceStatus.FAILED, error=str(e))
            raise
    
    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get a trace by ID."""
        return self._traces.get(trace_id)
    
    def replay_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """
        Replay a trace step by step.
        Returns timeline of operations for debugging.
        """
        trace = self.get_trace(trace_id)
        if not trace:
            return []
        
        timeline = []
        
        # Sort spans by start time
        sorted_spans = sorted(trace.spans, key=lambda s: s.start_time)
        
        for span in sorted_spans:
            timeline.append({
                "timestamp": span.start_time.isoformat(),
                "operation": span.operation_name,
                "type": span.trace_type.value,
                "duration_ms": span.duration_ms,
                "status": span.status.value,
                "input_summary": str(span.input_data)[:100] if span.input_data else None,
                "output_summary": str(span.output_data)[:100] if span.output_data else None,
                "error": span.error,
                "confidence": span.confidence_score
            })
        
        return timeline
    
    def diagnose_failure(self, trace_id: str) -> Dict[str, Any]:
        """
        Diagnose where a trace failed.
        Identifies the failing component (retriever, planner, LLM).
        """
        trace = self.get_trace(trace_id)
        if not trace:
            return {"error": "Trace not found"}
        
        diagnosis = {
            "trace_id": trace_id,
            "overall_status": trace.status.value,
            "total_duration_ms": trace.total_duration_ms,
            "failed_spans": [],
            "slow_spans": [],
            "low_confidence_spans": [],
            "root_cause": None
        }
        
        for span in trace.spans:
            # Find failures
            if span.status == TraceStatus.FAILED:
                diagnosis["failed_spans"].append({
                    "operation": span.operation_name,
                    "type": span.trace_type.value,
                    "error": span.error
                })
            
            # Find slow operations (>1 second)
            if span.duration_ms and span.duration_ms > 1000:
                diagnosis["slow_spans"].append({
                    "operation": span.operation_name,
                    "duration_ms": span.duration_ms
                })
            
            # Find low confidence
            if span.confidence_score and span.confidence_score < 0.5:
                diagnosis["low_confidence_spans"].append({
                    "operation": span.operation_name,
                    "confidence": span.confidence_score
                })
        
        # Determine root cause
        if diagnosis["failed_spans"]:
            first_failure = diagnosis["failed_spans"][0]
            diagnosis["root_cause"] = f"Failure in {first_failure['type']}: {first_failure['error']}"
        elif diagnosis["low_confidence_spans"]:
            worst = min(diagnosis["low_confidence_spans"], key=lambda x: x["confidence"])
            diagnosis["root_cause"] = f"Low confidence in {worst['operation']}: {worst['confidence']}"
        
        return diagnosis
    
    def _export_trace(self, trace: Trace):
        """Export trace to external endpoint."""
        try:
            import requests
            requests.post(
                self._export_endpoint,
                json=trace.to_dict(),
                timeout=5
            )
        except:
            pass  # Best effort export
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary metrics across all traces."""
        with self._lock:
            traces = list(self._traces.values())
        
        if not traces:
            return {"total_traces": 0}
        
        durations = [t.total_duration_ms for t in traces if t.total_duration_ms]
        confidences = [t.final_confidence for t in traces if t.final_confidence]
        
        return {
            "total_traces": len(traces),
            "completed": sum(1 for t in traces if t.status == TraceStatus.COMPLETED),
            "failed": sum(1 for t in traces if t.status == TraceStatus.FAILED),
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "p95_duration_ms": sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 20 else max(durations) if durations else 0,
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "total_tokens": sum(t.total_tokens for t in traces)
        }


# Singleton instance
observability = ObservabilityManager()


# Decorator for easy tracing
def traced(operation_name: str, trace_type: TraceType = TraceType.AGENT_STEP):
    """Decorator to trace a function."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            span_id = observability.start_span(
                operation_name,
                trace_type,
                input_data={"args_count": len(args), "kwargs_keys": list(kwargs.keys())}
            )
            try:
                result = func(*args, **kwargs)
                observability.end_span(span_id, output_data={"result_type": type(result).__name__})
                return result
            except Exception as e:
                observability.end_span(span_id, status=TraceStatus.FAILED, error=str(e))
                raise
        return wrapper
    return decorator
