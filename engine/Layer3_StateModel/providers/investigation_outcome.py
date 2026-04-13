"""
Investigation outcome classification for post-research updates.
"""

from __future__ import annotations

from typing import Dict, Any


def classify_outcome(new_information: float, contradictions: int) -> str:
    if float(new_information or 0.0) > 5.0:
        return "CONFIRMED"
    if int(contradictions or 0) > 0:
        return "REVISED"
    return "NULL_RESULT"


def build_outcome_record(
    question: str,
    new_information: float,
    contradictions: int,
) -> Dict[str, Any]:
    outcome = classify_outcome(new_information, contradictions)
    return {
        "question": str(question or ""),
        "outcome": outcome,
        "new_information": round(float(new_information or 0.0), 6),
        "contradictions": int(contradictions or 0),
    }


__all__ = ["classify_outcome", "build_outcome_record"]

