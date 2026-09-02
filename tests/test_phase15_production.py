"""
Phase 15: Production Hardening Test Suite
==========================================
Proves:
  1. Authentication: Rejects messages with bad signatures.
  2. Authorization: Rejects messages from unauthorized agents.
  3. Rate Limiting: Blocks run-away LLM loops (MAX_MESSAGES_PER_ROUND).
  4. Timeouts & Fallback: Gracefully degrades when primary LLM times out.
  5. Audit Log: Verifies correct structured logging of trace_ids.
"""

import asyncio
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from dip.pipeline.deliberation.reasoning.schema import AgentMessage, MessageType
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.pipeline.deliberation.reasoning.production import (
    PermissionError, RateLimitError, ResilienceManager, RunManifest
)

@pytest.mark.asyncio
async def test_authentication_rejects_bad_signature():
    bus = MessageBus(trace_id="TEST_RUN_001")
    
    # 1. Create a legitimate message but tamper with the signature
    msg = AgentMessage(
        message_id="msg_123",
        trace_id=bus.trace_id,
        round=1,
        sender="Security",
        receiver="BROADCAST",
        message_type=MessageType.HYPOTHESIS,
        claim="Hacked claim",
        reasoning_summary="...",
        signature="BAD_SIGNATURE"
    )
    
    # 2. Should raise PermissionError when publishing
    with pytest.raises(PermissionError, match="Signature mismatch"):
        await bus.publish(msg)

@pytest.mark.asyncio
async def test_authorization_rejects_unauthorized_action():
    bus = MessageBus(trace_id="TEST_RUN_002")
    
    # Contrarian is not authorized to write final beliefs according to PERMISSIONS
    is_authorized = bus.auth.check_permission("Contrarian", "write_belief")
    assert not is_authorized, "Contrarian should NOT be authorized to write beliefs"
    
    is_authorized_security = bus.auth.check_permission("Security", "write_belief")
    assert is_authorized_security, "Security SHOULD be authorized to write beliefs"

@pytest.mark.asyncio
async def test_rate_limiting_prevents_runaway_loops():
    bus = MessageBus(trace_id="TEST_RUN_003")
    
    # Security agent tries to publish more than MAX_MESSAGES_PER_ROUND (200)
    for i in range(200):
        msg_id = f"msg_{i}"
        msg = AgentMessage(
            message_id=msg_id,
            trace_id=bus.trace_id,
            round=1,
            sender="Security",
            receiver="BROADCAST",
            message_type=MessageType.HYPOTHESIS,
            claim="Runaway loop",
            reasoning_summary="...",
            signature=bus.auth.sign_message("Security", msg_id)
        )
        await bus.publish(msg)
        
    # The 201st message should trigger RateLimitError
    with pytest.raises(RateLimitError, match="exceeded MAX_MESSAGES_PER_ROUND"):
        msg_id = f"msg_201"
        msg = AgentMessage(
            message_id=msg_id,
            trace_id=bus.trace_id,
            round=1,
            sender="Security",
            receiver="BROADCAST",
            message_type=MessageType.HYPOTHESIS,
            claim="One too many",
            reasoning_summary="...",
            signature=bus.auth.sign_message("Security", msg_id)
        )
        await bus.publish(msg)

@pytest.mark.asyncio
async def test_llm_timeout_and_fallback():
    resilience = ResilienceManager()
    resilience.LLM_TIMEOUT_SECONDS = 0.5  # Artificial low timeout
    
    # 1. Primary Model (Simulate hang)
    async def slow_primary(model: str):
        if model == "gpt-4o-2024-08-06":
            await asyncio.sleep(2.0)  # Will timeout
            return "SUCCESS_PRIMARY"
        elif model == "gpt-3.5-turbo":
            return "SUCCESS_FALLBACK"
            
    result, mode = await resilience.with_timeout_and_fallback(
        coro=slow_primary,
        primary_model="gpt-4o-2024-08-06",
        fallback_model="gpt-3.5-turbo",
        mock_fallback=lambda: "DEGRADED_MOCK"
    )
    
    # Since primary timed out (2s > 0.5s) and fallback (3.5-turbo) completes instantly,
    # it should gracefully switch to FALLBACK.
    assert result == "SUCCESS_FALLBACK"
    assert mode == "FALLBACK"
    
    # 2. Both Models fail (Simulate catastrophic failure)
    async def completely_broken(model: str):
        raise ValueError("API is down")
        
    result2, mode2 = await resilience.with_timeout_and_fallback(
        coro=completely_broken,
        primary_model="gpt-4o-2024-08-06",
        fallback_model="gpt-3.5-turbo",
        mock_fallback=lambda: "DEGRADED_MOCK"
    )
    
    # Should use the deterministic mock fallback
    assert result2 == "DEGRADED_MOCK"
    assert mode2 == "DEGRADED"

def test_run_manifest_reproducibility():
    # Demonstrates that a deterministic manifest can be serialized
    manifest = RunManifest(
        run_id="REPLAY_RUN_005",
        model_version="gpt-4",
        prompt_version="v3.1",
        state_model_version="v3.0",
        config_version="2026-09-02",
        random_seed=42,
        evidence_snapshot="SNAP_005"
    )
    
    data = manifest.model_dump()
    assert data["run_id"] == "REPLAY_RUN_005"
    assert data["random_seed"] == 42
    
@pytest.mark.asyncio
async def test_audit_log_trace_id_propagation():
    trace_id = "AUDIT_RUN_006"
    bus = MessageBus(trace_id=trace_id)
    
    msg_id = "audit_1"
    msg = AgentMessage(
        message_id=msg_id,
        trace_id=trace_id,
        round=1,
        sender="Security",
        receiver="BROADCAST",
        message_type=MessageType.HYPOTHESIS,
        claim="Audit claim",
        reasoning_summary="...",
        signature=bus.auth.sign_message("Security", msg_id)
    )
    
    await bus.publish(msg)
    
    # Verify the audit log captured it
    assert len(bus.audit.log_buffer) == 1
    log_entry = bus.audit.log_buffer[0]
    
    assert log_entry.trace_id == trace_id
    assert log_entry.event == "MESSAGE_PUBLISHED"
    assert log_entry.agent == "Security"
    assert log_entry.message_id == msg_id
