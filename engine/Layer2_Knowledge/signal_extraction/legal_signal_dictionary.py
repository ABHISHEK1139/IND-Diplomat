"""
Geopolitical legal legitimacy phrase dictionary for Layer-2 extraction.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
import re


# Canonical phrase -> normalized signal type
LEGAL_SIGNALS: Dict[str, str] = {
    "territorial integrity": "defensive_justification",
    "sovereignty": "legitimacy_claim",
    "internal affairs": "intervention_warning",
    "self-defense": "pre_conflict_justification",
    "security commitment": "alliance_trigger",
    "provocation": "escalation_rhetoric",
    "separatist": "delegitimization",
    "violation": "legal_accusation",
    "one-china principle": "territorial_claim",
    "peace and stability": "diplomatic_pressure",
}


# Canonical phrase -> textual variants present in news/event feeds.
LEGAL_SIGNAL_ALIASES: Dict[str, Tuple[str, ...]] = {
    "territorial integrity": (
        "territorial integrity",
        "territorial claim",
        "territorial claims",
    ),
    "sovereignty": (
        "sovereignty",
        "sovereign rights",
        "violation of sovereignty",
    ),
    "internal affairs": (
        "internal affairs",
        "non-interference",
        "interference in domestic affairs",
    ),
    "self-defense": (
        "self-defense",
        "self defence",
        "right to self-defense",
        "defensive action",
    ),
    "security commitment": (
        "security commitment",
        "security guarantee",
        "alliance commitment",
        "security assurances",
    ),
    "provocation": (
        "provocation",
        "provocative action",
        "provocative move",
    ),
    "separatist": (
        "separatist",
        "separatism",
        "separatist activity",
    ),
    "violation": (
        "violation",
        "violated",
        "breach",
        "infringement",
    ),
    "one-china principle": (
        "one-china principle",
        "one china principle",
        "one china",
    ),
    "peace and stability": (
        "peace and stability",
        "regional stability",
        "stability in the taiwan strait",
    ),
}


# Fallback projection for terse machine-generated event text.
ACTION_PROJECTION_HINTS: Dict[str, str] = {
    "warned": "security commitment",
    "threatened": "self-defense",
    "threaten_military": "self-defense",
    "mobilized": "security commitment",
    "sanctioned": "violation",
    "accused": "violation",
    "coerced": "provocation",
}


def detect_legal_signal_hits(text: str) -> List[Dict[str, Any]]:
    """
    Detect legal-legitimacy phrase hits in text.

    Returns:
        List of dictionaries with canonical phrase, matched text, and offsets.
    """
    if not text:
        return []

    lowered = text.lower()
    hits: List[Dict[str, Any]] = []
    seen_phrases = set()

    for canonical_phrase, signal_type in LEGAL_SIGNALS.items():
        variants = LEGAL_SIGNAL_ALIASES.get(canonical_phrase, (canonical_phrase,))
        for variant in variants:
            pattern = r"\b" + re.escape(variant.lower()) + r"\b"
            match = re.search(pattern, lowered)
            if not match:
                continue
            if canonical_phrase in seen_phrases:
                break
            seen_phrases.add(canonical_phrase)
            hits.append(
                {
                    "phrase": canonical_phrase,
                    "signal_type": signal_type,
                    "matched_text": variant,
                    "strength": 0.92 if variant == canonical_phrase else 0.75,
                    "inferred": variant != canonical_phrase,
                    "start": match.start(),
                    "end": match.end(),
                }
            )
            break

    # Projection fallback: short event strings often only encode action labels.
    if not hits:
        for action_token, canonical_phrase in ACTION_PROJECTION_HINTS.items():
            pattern = r"\b" + re.escape(action_token.lower()) + r"\b"
            match = re.search(pattern, lowered)
            if not match:
                continue
            hits.append(
                {
                    "phrase": canonical_phrase,
                    "signal_type": LEGAL_SIGNALS[canonical_phrase],
                    "matched_text": action_token,
                    "strength": 0.45,
                    "inferred": True,
                    "start": match.start(),
                    "end": match.end(),
                }
            )
            break

    return hits


__all__ = [
    "LEGAL_SIGNALS",
    "LEGAL_SIGNAL_ALIASES",
    "ACTION_PROJECTION_HINTS",
    "detect_legal_signal_hits",
]
