"""
Pydantic schema for legal signals.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class LegalSignalRecord(BaseModel):
    provision_id: str = Field(min_length=1)
    provision_type: str = Field(min_length=1)
    actor: str = Field(default="unknown")
    modality: str = Field(default="may")
    strength: float = Field(ge=0.0, le=1.0)
    signal_type: str = Field(default="NONE")
    conditions: List[str] = Field(default_factory=list)
    exceptions: List[str] = Field(default_factory=list)
    overrides: List[Dict[str, str]] = Field(default_factory=list)
    cross_refs: List[str] = Field(default_factory=list)
    interpretive_terms: List[str] = Field(default_factory=list)
    jurisdiction_level: str = Field(default="statute")
    temporal_validity: Dict[str, Optional[str]] = Field(default_factory=dict)
    burden_standard: Dict[str, str] = Field(default_factory=dict)
    remedy_hint: str = Field(default="unknown")
    original_text: str = Field(min_length=1)
    review_required: bool = False

