from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class MessageType(str, Enum):
    OBSERVATION = "OBSERVATION"
    HYPOTHESIS = "HYPOTHESIS"
    EVIDENCE_REQUEST = "EVIDENCE_REQUEST"
    EVIDENCE_RESPONSE = "EVIDENCE_RESPONSE"
    CHALLENGE = "CHALLENGE"
    REBUTTAL = "REBUTTAL"
    ENDORSEMENT = "ENDORSEMENT"
    DISSENT = "DISSENT"
    REVISION = "REVISION"
    VERIFICATION_REQUEST = "VERIFICATION_REQUEST"
    VERIFICATION_RESULT = "VERIFICATION_RESULT"
    FINAL_RECOMMENDATION = "FINAL_RECOMMENDATION"

class Belief(BaseModel):
    state: str
    probability: float
    
class BeliefLedger(BaseModel):
    agent: str
    beliefs: List[Belief]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class AgentMessage(BaseModel):
    message_id: str
    trace_id: str = "UNKNOWN_TRACE"  # Phase 15: Run reproducibility and tracing
    round: int
    sender: str
    receiver: str
    message_type: MessageType
    claim: str
    state: Optional[str] = None
    probability: Optional[float] = None
    confidence: Optional[float] = None
    evidence_ids: List[str] = Field(default_factory=list)
    counter_evidence: List[str] = Field(default_factory=list)
    reasoning_summary: str
    signature: Optional[str] = None  # Phase 15: Agent authentication signature
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class EvidenceNode(BaseModel):
    evidence_id: str
    observation_id: str
    source: str
    reliability: float
    content: str
    timestamp: str
