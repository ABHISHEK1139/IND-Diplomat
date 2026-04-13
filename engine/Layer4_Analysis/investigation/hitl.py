"""
Human-in-the-Loop (HITL) Intervention Layer
Implements reactive intervention when confidence scores fall below thresholds.
Uses LangGraph-style interrupts for reasoning loop pauses.
"""

from typing import List, Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import uuid


class InterventionType(Enum):
    """Types of intervention requests."""
    APPROVAL_REQUIRED = "approval_required"
    CONTEXT_NEEDED = "context_needed"
    AMBIGUITY_RESOLUTION = "ambiguity_resolution"
    SENSITIVE_TOPIC = "sensitive_topic"
    LOW_CONFIDENCE = "low_confidence"
    CONFLICT_DETECTED = "conflict_detected"
    MANUAL_OVERRIDE = "manual_override"


class InterventionStatus(Enum):
    """Status of an intervention request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    TIMEOUT = "timeout"
    ESCALATED = "escalated"


@dataclass
class InterventionRequest:
    """A request for human intervention."""
    request_id: str
    intervention_type: InterventionType
    query: str
    proposed_response: str
    confidence_score: float
    
    # Reason for intervention
    reason: str
    sources: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]
    
    # Timing
    created_at: datetime
    timeout_at: datetime
    resolved_at: Optional[datetime] = None
    
    # Resolution
    status: InterventionStatus = InterventionStatus.PENDING
    human_feedback: Optional[str] = None
    modified_response: Optional[str] = None
    approved_by: Optional[str] = None


@dataclass
class HITLConfig:
    """Configuration for HITL system."""
    # Thresholds
    min_confidence_threshold: float = 0.70
    sensitive_topic_threshold: float = 0.85
    conflict_auto_escalate: bool = True
    
    # Timeouts
    default_timeout_minutes: int = 30
    urgent_timeout_minutes: int = 5
    
    # Escalation
    max_pending_before_escalate: int = 10
    escalation_contacts: List[str] = field(default_factory=list)


class HITLManager:
    """
    Human-in-the-Loop Manager for diplomatic intelligence.
    
    Pauses reasoning when:
    - Confidence falls below threshold
    - Sensitive topics detected
    - Source conflicts require resolution
    - Manual approval required for high-stakes decisions
    """
    
    # Sensitive topic keywords
    SENSITIVE_TOPICS = [
        "classified", "confidential", "secret", "top secret",
        "nuclear", "biological", "chemical",
        "intelligence", "espionage", "covert",
        "assassination", "coup", "invasion",
        "sanctions violation", "embargo", "blacklist"
    ]
    
    def __init__(self, config: HITLConfig = None):
        self.config = config or HITLConfig()
        self._pending_interventions: Dict[str, InterventionRequest] = {}
        self._resolved_interventions: Dict[str, InterventionRequest] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._intervention_queue = asyncio.Queue() if asyncio else None
    
    def should_intervene(
        self,
        query: str,
        proposed_response: str,
        confidence: float,
        sources: List[Dict] = None,
        conflicts: List[Dict] = None
    ) -> tuple[bool, InterventionType, str]:
        """
        Check if human intervention is needed.
        Returns (should_intervene, type, reason).
        """
        # Low confidence check
        if confidence < self.config.min_confidence_threshold:
            return True, InterventionType.LOW_CONFIDENCE, \
                f"Confidence score {confidence:.2f} below threshold {self.config.min_confidence_threshold}"
        
        # Sensitive topic check
        combined_text = f"{query} {proposed_response}".lower()
        for topic in self.SENSITIVE_TOPICS:
            if topic in combined_text:
                if confidence < self.config.sensitive_topic_threshold:
                    return True, InterventionType.SENSITIVE_TOPIC, \
                        f"Sensitive topic '{topic}' detected with confidence {confidence:.2f}"
        
        # Conflict check
        if conflicts and len(conflicts) > 0 and self.config.conflict_auto_escalate:
            return True, InterventionType.CONFLICT_DETECTED, \
                f"{len(conflicts)} source conflict(s) require human resolution"
        
        return False, None, ""
    
    async def request_intervention(
        self,
        query: str,
        proposed_response: str,
        confidence: float,
        intervention_type: InterventionType,
        reason: str,
        sources: List[Dict] = None,
        conflicts: List[Dict] = None,
        urgent: bool = False
    ) -> InterventionRequest:
        """
        Request human intervention and pause processing.
        """
        request_id = str(uuid.uuid4())[:12]
        
        timeout_minutes = self.config.urgent_timeout_minutes if urgent else self.config.default_timeout_minutes
        
        request = InterventionRequest(
            request_id=request_id,
            intervention_type=intervention_type,
            query=query,
            proposed_response=proposed_response,
            confidence_score=confidence,
            reason=reason,
            sources=sources or [],
            conflicts=conflicts or [],
            created_at=datetime.now(),
            timeout_at=datetime.now() + timedelta(minutes=timeout_minutes)
        )
        
        self._pending_interventions[request_id] = request
        
        # Notify callbacks
        if intervention_type.value in self._callbacks:
            await self._callbacks[intervention_type.value](request)
        
        return request
    
    async def wait_for_resolution(
        self,
        request_id: str,
        poll_interval_seconds: float = 1.0
    ) -> InterventionRequest:
        """
        Wait for human intervention to be resolved.
        This is the "pause" in the reasoning loop.
        """
        while True:
            request = self._pending_interventions.get(request_id)
            
            if not request:
                # Already resolved
                return self._resolved_interventions.get(request_id)
            
            # Check timeout
            if datetime.now() > request.timeout_at:
                request.status = InterventionStatus.TIMEOUT
                self._move_to_resolved(request_id)
                return request
            
            # Check if resolved
            if request.status != InterventionStatus.PENDING:
                self._move_to_resolved(request_id)
                return request
            
            await asyncio.sleep(poll_interval_seconds)
    
    def resolve_intervention(
        self,
        request_id: str,
        status: InterventionStatus,
        feedback: str = None,
        modified_response: str = None,
        approved_by: str = None
    ) -> bool:
        """
        Resolve an intervention request (called by human).
        """
        if request_id not in self._pending_interventions:
            return False
        
        request = self._pending_interventions[request_id]
        request.status = status
        request.human_feedback = feedback
        request.modified_response = modified_response
        request.approved_by = approved_by
        request.resolved_at = datetime.now()
        
        return True
    
    def approve(
        self,
        request_id: str,
        approved_by: str,
        feedback: str = None
    ) -> bool:
        """Quick approve an intervention."""
        return self.resolve_intervention(
            request_id,
            InterventionStatus.APPROVED,
            feedback=feedback,
            approved_by=approved_by
        )
    
    def reject(
        self,
        request_id: str,
        rejected_by: str,
        reason: str
    ) -> bool:
        """Reject an intervention."""
        return self.resolve_intervention(
            request_id,
            InterventionStatus.REJECTED,
            feedback=reason,
            approved_by=rejected_by
        )
    
    def modify(
        self,
        request_id: str,
        modified_by: str,
        new_response: str,
        feedback: str = None
    ) -> bool:
        """Modify the proposed response."""
        return self.resolve_intervention(
            request_id,
            InterventionStatus.MODIFIED,
            feedback=feedback,
            modified_response=new_response,
            approved_by=modified_by
        )
    
    def _move_to_resolved(self, request_id: str):
        """Move intervention from pending to resolved."""
        if request_id in self._pending_interventions:
            request = self._pending_interventions.pop(request_id)
            self._resolved_interventions[request_id] = request
    
    def get_pending_interventions(self) -> List[InterventionRequest]:
        """Get all pending intervention requests."""
        return list(self._pending_interventions.values())
    
    def get_intervention(self, request_id: str) -> Optional[InterventionRequest]:
        """Get a specific intervention by ID."""
        return self._pending_interventions.get(request_id) or \
               self._resolved_interventions.get(request_id)
    
    def register_callback(
        self,
        intervention_type: InterventionType,
        callback: Callable[[InterventionRequest], Awaitable[None]]
    ):
        """Register callback for intervention type."""
        self._callbacks[intervention_type.value] = callback
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get HITL statistics."""
        all_requests = list(self._pending_interventions.values()) + \
                       list(self._resolved_interventions.values())
        
        if not all_requests:
            return {"total": 0}
        
        resolved = list(self._resolved_interventions.values())
        resolution_times = [
            (r.resolved_at - r.created_at).total_seconds()
            for r in resolved
            if r.resolved_at
        ]
        
        return {
            "total": len(all_requests),
            "pending": len(self._pending_interventions),
            "resolved": len(self._resolved_interventions),
            "approved": sum(1 for r in resolved if r.status == InterventionStatus.APPROVED),
            "rejected": sum(1 for r in resolved if r.status == InterventionStatus.REJECTED),
            "modified": sum(1 for r in resolved if r.status == InterventionStatus.MODIFIED),
            "timeout": sum(1 for r in resolved if r.status == InterventionStatus.TIMEOUT),
            "avg_resolution_seconds": sum(resolution_times) / len(resolution_times) if resolution_times else 0,
            "by_type": {
                t.value: sum(1 for r in all_requests if r.intervention_type == t)
                for t in InterventionType
            }
        }
    
    def format_intervention_for_ui(self, request: InterventionRequest) -> Dict[str, Any]:
        """Format intervention request for UI display."""
        return {
            "id": request.request_id,
            "type": request.intervention_type.value.replace("_", " ").title(),
            "status": request.status.value,
            "query": request.query[:100] + "..." if len(request.query) > 100 else request.query,
            "proposed_response": request.proposed_response[:200] + "..." if len(request.proposed_response) > 200 else request.proposed_response,
            "confidence": f"{request.confidence_score:.0%}",
            "reason": request.reason,
            "conflicts_count": len(request.conflicts),
            "sources_count": len(request.sources),
            "created": request.created_at.strftime("%Y-%m-%d %H:%M"),
            "timeout_in": str(request.timeout_at - datetime.now()).split(".")[0] if request.status == InterventionStatus.PENDING else None,
            "urgent": (request.timeout_at - request.created_at).total_seconds() < 600
        }


# Singleton instance
hitl_manager = HITLManager()


# LangGraph-style interrupt decorator
def interruptible(
    confidence_getter: Callable = None,
    min_confidence: float = 0.70
):
    """
    Decorator to make a function interruptible based on confidence.
    Similar to LangGraph interrupts.
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Execute function
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
            # Get confidence
            confidence = confidence_getter(result) if confidence_getter else 1.0
            
            # Check if intervention needed
            should_pause, int_type, reason = hitl_manager.should_intervene(
                query=str(kwargs.get("query", "")),
                proposed_response=str(result),
                confidence=confidence
            )
            
            if should_pause:
                request = await hitl_manager.request_intervention(
                    query=str(kwargs.get("query", "")),
                    proposed_response=str(result),
                    confidence=confidence,
                    intervention_type=int_type,
                    reason=reason
                )
                
                resolved = await hitl_manager.wait_for_resolution(request.request_id)
                
                if resolved.status == InterventionStatus.MODIFIED:
                    return resolved.modified_response
                elif resolved.status == InterventionStatus.REJECTED:
                    raise InterventionRejectedException(resolved.human_feedback)
            
            return result
        
        return wrapper
    return decorator


class InterventionRejectedException(Exception):
    """Raised when human rejects the proposed response."""
    pass
