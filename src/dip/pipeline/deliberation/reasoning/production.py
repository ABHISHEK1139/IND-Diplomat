"""
Phase 15: Production + Safety Hardening
========================================
Implements:
  - Authentication (Agent Identities, Signatures)
  - Authorization (Permission Matrices)
  - Resiliency (Rate Limits, Timeouts, Retries, Fallbacks)
  - Observability (Trace IDs, Run Manifests, Audit Logs)
  - Failure Recovery
"""

import json
import logging
import asyncio
import uuid
import hashlib
from typing import Dict, List, Any, Optional, Callable
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from dip.pipeline.deliberation.reasoning.schema import AgentMessage, MessageType

logger = logging.getLogger("Layer15.Production")

# ─── Reproducibility & Audit ──────────────────────────────────────────────────

class RunManifest(BaseModel):
    """Stores all parameters necessary to deterministically replay a run."""
    run_id: str = Field(default_factory=lambda: f"RUN_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}")
    model_version: str = "gpt-4o-2024-08-06"
    prompt_version: str = "v3.1"
    state_model_version: str = "v3.0"
    config_version: str = "2026-09-02"
    random_seed: int = 42
    evidence_snapshot: str = ""
    start_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "RUNNING"


class AuditEvent(BaseModel):
    """Structured audit log entry."""
    trace_id: str
    event: str
    agent: str
    message_id: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: Dict[str, Any] = Field(default_factory=dict)


class AuditLogger:
    """Handles structured logging to a secure destination."""
    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.log_buffer: List[AuditEvent] = []
        
    def log(self, event: str, agent: str, message_id: Optional[str] = None, 
            evidence_ids: Optional[List[str]] = None, **details):
        entry = AuditEvent(
            trace_id=self.trace_id,
            event=event,
            agent=agent,
            message_id=message_id,
            evidence_ids=evidence_ids or [],
            details=details
        )
        self.log_buffer.append(entry)
        # In a real system, this flushes to Elasticsearch/Splunk
        logger.debug(f"[AUDIT] {json.dumps(entry.model_dump())}")


# ─── Auth & Authorization ─────────────────────────────────────────────────────

class AgentIdentity(BaseModel):
    agent_id: str
    service: str = "ind_diplomat"
    key_id: str


class PermissionError(Exception):
    pass


class AuthManager:
    """Manages Agent Identity and RBAC rules."""
    
    # What is each agent allowed to do?
    PERMISSIONS = {
        "Security": {"read_evidence", "write_belief", "trigger_debate"},
        "Diplomacy": {"read_evidence", "write_belief", "trigger_debate"},
        "Economic": {"read_evidence", "write_belief", "trigger_debate"},
        "Domestic": {"read_evidence", "write_belief", "trigger_debate"},
        "Alliance": {"read_evidence", "write_belief", "trigger_debate"},
        "Strategy": {"read_evidence", "write_belief", "trigger_debate"},
        "Contrarian": {"read_evidence", "trigger_debate"},  # Cannot write final beliefs
        "Verification": {"read_evidence", "trigger_debate"},
        "Orchestrator": {"read_evidence", "write_belief", "trigger_debate"},
        "DeterministicGate": {"read_evidence", "write_belief", "trigger_debate", "modify_gate"},
    }
    
    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self._keys = {
            name: hashlib.sha256(f"{name}_{trace_id}_secret".encode()).hexdigest()
            for name in self.PERMISSIONS.keys()
        }
        
    def sign_message(self, agent: str, message_id: str) -> str:
        """Create a cryptographic signature for an agent's message."""
        secret = self._keys.get(agent, "unknown")
        return hashlib.sha256(f"{agent}_{message_id}_{secret}".encode()).hexdigest()
        
    def verify_message(self, msg: AgentMessage) -> bool:
        """Verify the signature and identity of the sender."""
        expected = self.sign_message(msg.sender, msg.message_id)
        if msg.signature != expected:
            logger.error(f"[Auth] Signature mismatch for {msg.message_id} from {msg.sender}")
            return False
        return True
        
    def check_permission(self, agent: str, action: str) -> bool:
        """Check if an agent is authorized to perform an action."""
        perms = self.PERMISSIONS.get(agent, set())
        if action not in perms:
            logger.error(f"[Auth] Agent '{agent}' denied action '{action}'")
            return False
        return True


# ─── Resiliency & Fault Tolerance ─────────────────────────────────────────────

class RateLimitError(Exception):
    pass

class CostMetrics(BaseModel):
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_seconds: float = 0.0
    evidence_calls: int = 0
    retries: int = 0
    
class ResilienceManager:
    """Handles Rate Limiting, Timeouts, Retries, Fallbacks, and System Cost Metrics."""
    
    MAX_ROUNDS = 4
    MAX_MESSAGES_PER_ROUND = 200
    MAX_EVIDENCE_REQUESTS = 10
    LLM_TIMEOUT_SECONDS = 30
    
    def __init__(self):
        self.message_counts: Dict[str, int] = {}
        self.evidence_requests: Dict[str, int] = {}
        self.round_count = 1
        self.metrics = CostMetrics()
        
    def record_llm_call(self, input_tokens: int, output_tokens: int, latency: float, retried: bool = False):
        """Track LLM costs as a first-class production metric."""
        self.metrics.llm_calls += 1
        self.metrics.input_tokens += input_tokens
        self.metrics.output_tokens += output_tokens
        self.metrics.latency_seconds += latency
        if retried:
            self.metrics.retries += 1
        
    def check_rate_limit(self, agent: str, message_type: MessageType, current_round: int):
        """Raises RateLimitError if limits are exceeded, preventing runaway LLM loops."""
        if current_round > self.MAX_ROUNDS:
            raise RateLimitError(f"Debate exceeded MAX_ROUNDS ({self.MAX_ROUNDS})")
            
        if self.round_count != current_round:
            self.round_count = current_round
            self.message_counts = {}
            
        self.message_counts[agent] = self.message_counts.get(agent, 0) + 1
        if self.message_counts[agent] > self.MAX_MESSAGES_PER_ROUND:
            raise RateLimitError(f"Agent {agent} exceeded MAX_MESSAGES_PER_ROUND")
            
        if message_type == MessageType.EVIDENCE_REQUEST:
            self.evidence_requests[agent] = self.evidence_requests.get(agent, 0) + 1
            if self.evidence_requests[agent] > self.MAX_EVIDENCE_REQUESTS:
                raise RateLimitError(f"Agent {agent} exceeded MAX_EVIDENCE_REQUESTS")

    async def with_timeout_and_fallback(
        self, 
        coro, 
        primary_model: str, 
        fallback_model: str, 
        mock_fallback: Callable
    ):
        """
        Executes an LLM call with timeouts, auto-retry on fallback, 
        and ultimately a degraded mock mode if all models fail.
        """
        try:
            # 1. Primary Model with Timeout
            return await asyncio.wait_for(coro(primary_model), timeout=self.LLM_TIMEOUT_SECONDS), "PRIMARY"
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"[Resilience] Primary model '{primary_model}' failed ({type(e).__name__}). Switching to fallback.")
            
            try:
                # 2. Fallback Model
                return await asyncio.wait_for(coro(fallback_model), timeout=self.LLM_TIMEOUT_SECONDS), "FALLBACK"
            except Exception as e2:
                logger.error(f"[Resilience] Fallback model '{fallback_model}' failed ({type(e2).__name__}). Using DEGRADED mode.")
                
                # 3. Degraded / Deterministic Fallback
                return mock_fallback(), "DEGRADED"

