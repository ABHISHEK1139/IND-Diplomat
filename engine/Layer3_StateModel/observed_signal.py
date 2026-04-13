"""
Observed Signal — the belief unit for Layer-4 reasoning.
=========================================================

A signal is NOT a boolean flag.
A signal is a **graded belief** about the world:

    confidence * reliability * recency * intensity

This structure is the "sensory cortex" — it translates raw Layer-3
telemetry into something the council can reason over probabilistically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value or 0.0)))


@dataclass
class ObservedSignal:
    """
    Structured belief about a single intelligence signal.

    Attributes
    ----------
    name : str
        Canonical signal token (e.g. ``SIG_FORCE_POSTURE``).
    confidence : float
        Overall belief strength in [0, 1].
        ``confidence = membership × reliability × recency``
    membership : float
        Fuzzy membership from the underlying telemetry value.
        How strongly the raw sensor data suggests this signal is active.
    reliability : float
        Source trustworthiness — data_confidence, source_agreement.
    recency : float
        Time-decay factor.  1.0 = fresh data, → 0.0 as data ages.
    intensity : float
        Magnitude of the underlying activity (raw telemetry value).
    sources : list[str]
        Provenance chain — which datasets contributed.
    dimension : str
        Which analytical dimension this signal belongs to
        (CAPABILITY, INTENT, STABILITY, COST).
    """

    name: str
    confidence: float = 0.0
    membership: float = 0.0
    reliability: float = 0.5
    recency: float = 0.5
    intensity: float = 0.0
    sources: List[str] = field(default_factory=list)
    dimension: str = "UNKNOWN"
    namespace: str = "empirical"  # "empirical" | "legal" | "derived"

    def __post_init__(self):
        self.name = str(self.name or "").strip().upper()
        self.confidence = _clip01(self.confidence)
        self.membership = _clip01(self.membership)
        self.reliability = _clip01(self.reliability)
        self.recency = _clip01(self.recency)
        self.intensity = _clip01(self.intensity)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "confidence": round(self.confidence, 4),
            "membership": round(self.membership, 4),
            "reliability": round(self.reliability, 4),
            "recency": round(self.recency, 4),
            "intensity": round(self.intensity, 4),
            "sources": list(self.sources),
            "dimension": self.dimension,
            "namespace": self.namespace,
        }

    def __repr__(self) -> str:
        return (
            f"ObservedSignal({self.name}, "
            f"conf={self.confidence:.3f}, "
            f"memb={self.membership:.3f}, "
            f"rel={self.reliability:.3f}, "
            f"rec={self.recency:.3f}, "
            f"int={self.intensity:.3f}, "
            f"dim={self.dimension}, "
            f"ns={self.namespace})"
        )
