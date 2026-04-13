"""
Pydantic schema for state model outputs.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class StateModelRecord(BaseModel):
    actors: List[str] = Field(default_factory=list)
    recent_events: List[str] = Field(default_factory=list)
    diplomatic_tension: float = Field(default=0.0, ge=0.0, le=1.0)
    legal_signals: List[str] = Field(default_factory=list)
    trade_dependency: float = Field(default=0.0, ge=0.0)
    military_balance: float = Field(default=0.0, ge=0.0)
    evidence_sources: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    generated_at: Optional[str] = None
    metadata: Dict[str, object] = Field(default_factory=dict)

