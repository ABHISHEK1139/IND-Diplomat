"""ObservedSignal dataclass used by next-gen Layer-4 modules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ObservedSignal:
    entity: str
    action: str
    intensity: float = 0.5  # normalized 0.0-1.0
    confidence: float = 0.5  # normalized 0.0-1.0
    source: Optional[str] = None
    timestamp: Optional[str] = None
    domain: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "entity": self.entity,
            "action": self.action,
            "intensity": float(self.intensity),
            "confidence": float(self.confidence),
            "source": self.source,
            "timestamp": self.timestamp,
            "domain": self.domain,
        }
