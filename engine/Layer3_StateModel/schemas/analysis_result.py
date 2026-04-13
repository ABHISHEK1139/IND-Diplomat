
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class EvidenceReference:
    """Reference to a specific piece of evidence used in analysis."""
    source_id: str  # e.g., "sipri_import_row_123" or "engram_abc123"
    source_type: str # "database", "rag", "sensor"
    description: str # Brief description of the evidence
    confidence: float = 1.0 # Confidence in this specific evidence piece

@dataclass
class AnalysisResult:
    """
    Standardized result object for all intelligence analysis layers.
    Ensures consistent communication between Ministers, Coordinator, and API.
    """
    agent_name: str
    summary_text: str
    detailed_reasoning: str
    confidence_score: float  # 0.0 to 1.0
    evidence_used: List[EvidenceReference] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "summary_text": self.summary_text,
            "detailed_reasoning": self.detailed_reasoning,
            "confidence_score": self.confidence_score,
            "evidence_used": [
                {
                    "source_id": e.source_id,
                    "source_type": e.source_type,
                    "description": e.description,
                    "confidence": e.confidence
                } for e in self.evidence_used
            ],
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
