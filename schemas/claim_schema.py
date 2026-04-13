"""
Pydantic schema for extracted claims.
"""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field


class ClaimRecord(BaseModel):
    claim_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    actor: str = ""
    target: str = ""
    predicate: str = Field(default="statement", min_length=1)
    polarity: str = Field(default="neutral", pattern="^(positive|negative|neutral)$")
    claim_text: str = Field(min_length=3)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    claim_date: Optional[str] = None
    metadata: Dict[str, object] = Field(default_factory=dict)

