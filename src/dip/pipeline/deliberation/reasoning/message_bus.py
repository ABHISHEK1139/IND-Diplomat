import asyncio
import logging
import uuid
from typing import List, Dict, Callable, Awaitable
from datetime import datetime

from dip.pipeline.deliberation.reasoning.schema import AgentMessage, MessageType, BeliefLedger, EvidenceNode

logger = logging.getLogger("Layer4.MessageBus")

class MessageBus:
    """
    Central hub for structured agent communication.
    Supports pub/sub architecture using Python asyncio queues as a prototype
    for future Redis Streams / Kafka integration.
    """
    def __init__(self, trace_id: str = "UNKNOWN_TRACE"):
        # Phase 15: Production Hardening
        from dip.pipeline.deliberation.reasoning.production import AuthManager, AuditLogger, ResilienceManager, PermissionError
        self.trace_id = trace_id
        self.auth = AuthManager(trace_id)
        self.audit = AuditLogger(trace_id)
        self.resilience = ResilienceManager()
        self.PermissionError = PermissionError

        # Level 1 - Global Evidence Memory
        self.evidence_memory: Dict[str, EvidenceNode] = {}
        
        # Level 2 - Agent Memory
        self.agent_memory: Dict[str, List[BeliefLedger]] = {}
        
        # Level 3 - Debate Memory (the trace)
        self.debate_memory: List[AgentMessage] = []
        
        # Subscriptions
        # Dict[topic, List[callback]]
        self.subscriptions: Dict[str, List[Callable[[AgentMessage], Awaitable[None]]]] = {}
        
        self.queue = asyncio.Queue()
        self._running = False
        self._worker_task = None
        
    def add_evidence(self, node: EvidenceNode):
        self.evidence_memory[node.evidence_id] = node
        logger.debug(f"[Global Memory] Added evidence {node.evidence_id}")

    def update_agent_belief(self, ledger: BeliefLedger):
        if ledger.agent not in self.agent_memory:
            self.agent_memory[ledger.agent] = []
        self.agent_memory[ledger.agent].append(ledger)
        logger.debug(f"[Agent Memory] Updated belief for {ledger.agent}")

    def subscribe(self, message_type, callback: Callable[[AgentMessage], Awaitable[None]]):
        topic = message_type.value if hasattr(message_type, "value") else message_type
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        self.subscriptions[topic].append(callback)
        
    def subscribe_to_all(self, callback: Callable[[AgentMessage], Awaitable[None]]):
        self.subscribe("ALL", callback)

    async def publish(self, message: AgentMessage):
        """Publish a message to the bus, validating auth and rate limits first."""
        # 1. Check Rate Limits
        self.resilience.check_rate_limit(message.sender, message.message_type, message.round)
        
        # 2. Verify Identity Signature
        if not self.auth.verify_message(message):
            raise self.PermissionError(f"Signature mismatch for {message.sender}")
            
        # 3. Log to Audit
        self.audit.log(
            event="MESSAGE_PUBLISHED", 
            agent=message.sender, 
            message_id=message.message_id, 
            evidence_ids=message.evidence_ids,
            message_type=message.message_type.value
        )
        
        # 4. Store and Route
        self.debate_memory.append(message)
        await self.queue.put(message)

    async def _worker(self):
        while self._running:
            try:
                message: AgentMessage = await self.queue.get()
                
                # Route to specific type subscribers
                topic = message.message_type.value
                subs = self.subscriptions.get(topic, [])
                
                # Route to wildcard subscribers
                subs.extend(self.subscriptions.get("ALL", []))
                
                for sub in subs:
                    # We can spawn tasks or run sequentially. Let's run concurrently.
                    asyncio.create_task(sub(message))
                    
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing message {message.message_id}: {e}")

    async def start(self):
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("MessageBus started.")

    async def stop(self):
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
        logger.info("MessageBus stopped.")
