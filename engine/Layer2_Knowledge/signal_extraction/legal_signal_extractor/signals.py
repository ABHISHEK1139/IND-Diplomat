"""
Power-word signal definitions for legal micro-signal extraction.

The extractor intentionally uses a constrained set of categories so this
remains a geopolitical feature (legitimacy channel), not a full legal expert.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


LEGAL_SIGNALS: Dict[str, Dict[str, Any]] = {
    "OBLIGATION": {
        "keywords": ["shall", "must", "undertakes to", "obliged to"],
        "weight": 1.0,
        "meaning": "CONSTRAINT: Action is required.",
        "modality": "shall",
        "provision_type": "duty",
    },
    "PROHIBITION": {
        "keywords": ["shall not", "must not", "prohibited", "refrain from", "cannot"],
        "weight": -1.0,
        "meaning": "CONSTRAINT: Action is banned.",
        "modality": "prohibited",
        "provision_type": "right",
    },
    "PERMISSION": {
        "keywords": ["may", "can", "entitled to", "has the right to"],
        "weight": 0.5,
        "meaning": "FREEDOM: Strategic option available.",
        "modality": "may",
        "provision_type": "power",
    },
    "JUSTIFICATION": {
        "keywords": [
            "self-defense",
            "national security",
            "sovereignty",
            "public order",
            "emergency",
        ],
        "weight": 2.0,
        "meaning": "ESCALATION: Narrative basis for aggressive action.",
        "modality": "may",
        "provision_type": "exception",
    },
    "LOOPHOLE": {
        "keywords": ["except", "unless", "subject to", "notwithstanding", "provided that"],
        "weight": 0.8,
        "meaning": "FLEXIBILITY: Potential legal carve-out.",
        "modality": "may",
        "provision_type": "exception",
    },
}

SIGNAL_PRIORITY: List[str] = [
    "PROHIBITION",
    "OBLIGATION",
    "PERMISSION",
    "JUSTIFICATION",
    "LOOPHOLE",
]

INTERPRETIVE_TERMS = {
    "reasonable",
    "necessary",
    "proportionate",
    "appropriate",
    "public interest",
    "public order",
}

CONDITIONAL_KEYWORDS = [
    "if",
    "when",
    "where",
    "during",
    "in case of",
    "provided that",
]

EXCEPTION_KEYWORDS = ["except", "unless", "provided that", "provided further"]

OVERRIDE_KEYWORDS = ["notwithstanding", "subject to"]

REFERENCE_PATTERN = re.compile(
    r"\b(?:Article|Art\.|Section|Sec\.|Rule|Regulation)\s*[A-Za-z0-9().-]+",
    re.IGNORECASE,
)


def detect_signal_hits(clause_text: str) -> List[Dict[str, Any]]:
    """
    Return all signal hits for a clause.
    """
    lower = clause_text.lower()
    hits: List[Dict[str, Any]] = []

    for signal_type, data in LEGAL_SIGNALS.items():
        for keyword in data["keywords"]:
            pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
            if re.search(pattern, lower):
                hits.append(
                    {
                        "type": signal_type,
                        "trigger_word": keyword,
                        "weight": float(data["weight"]),
                        "implication": data["meaning"],
                        "modality": data["modality"],
                        "provision_type": data["provision_type"],
                    }
                )
    return hits


def choose_primary_signal(hits: List[Dict[str, Any]]) -> str:
    """
    Pick a primary signal using fixed legal priority order.
    """
    if not hits:
        return "NONE"

    seen = {hit["type"] for hit in hits}
    for signal_type in SIGNAL_PRIORITY:
        if signal_type in seen:
            return signal_type
    return hits[0]["type"]

