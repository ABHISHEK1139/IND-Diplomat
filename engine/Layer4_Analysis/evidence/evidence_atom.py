"""
Atomic evidence unit for grounding checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class EvidenceAtom:
    source_id: str
    source_type: str
    timestamp: str
    signals: List[str] = field(default_factory=list)


__all__ = ["EvidenceAtom"]
