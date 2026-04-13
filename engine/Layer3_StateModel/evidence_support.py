"""
Evidence Support — document-grounded belief modulation.
========================================================

RAG-retrieved documents can *strengthen or weaken* projected beliefs.
Before this module, documents only fed verification (CoVe).
Now they feed perception too.

Design
------
For each projected signal, scan retrieved documents for supporting
evidence.  Return a multiplier in the range ``[0.85, 1.25]``:

* **0 matches** → ``0.85``  (mild penalty — no documentary support)
* **1 match**   → ``1.10``  (modest boost)
* **≥2 matches** → ``1.25``  (strong convergence boost)

The multiplier is applied to the signal's composite confidence:

    confidence = membership × reliability × recency × evidence_support

This means retrieved text sources now **strengthen or weaken signals**
rather than acting only as a post-hoc fact check.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

# ── Signal token to keyword map ───────────────────────────────────────
# Each signal token is associated with terms likely to appear in
# supporting documents.  Matching is case-insensitive word containment.
_SIGNAL_KEYWORDS: Dict[str, List[str]] = {
    "SIG_MIL_ESCALATION": ["military", "escalation", "troops", "deployment", "offensive", "mobilization"],
    "SIG_MIL_MOBILIZATION": ["mobilization", "troops", "reserves", "callup", "military buildup"],
    "SIG_FORCE_POSTURE": ["force posture", "forward deployment", "military presence", "naval", "airforce"],
    "SIG_LOGISTICS_PREP": ["logistics", "supply chain", "stockpiling", "ammunition", "materiel"],
    "SIG_CYBER_ACTIVITY": ["cyber", "hack", "intrusion", "cyberattack", "malware", "digital"],
    "SIG_DIP_HOSTILITY": ["hostility", "hostile rhetoric", "diplomatic tension", "ambassador recall"],
    "SIG_DIP_HOSTILE_RHETORIC": ["rhetoric", "hostile", "threat", "denounce"],
    "SIG_ALLIANCE_SHIFT": ["alliance", "realignment", "pact", "coalition", "mutual defense"],
    "SIG_ALLIANCE_ACTIVATION": ["alliance activation", "collective defense", "treaty invocation", "nato article"],
    "SIG_NEGOTIATION_BREAKDOWN": ["negotiation", "breakdown", "talks collapse", "diplomatic failure", "stalemate"],
    "SIG_COERCIVE_PRESSURE": ["coercion", "sanctions", "blockade", "embargo", "economic pressure"],
    "SIG_COERCIVE_BARGAINING": ["coercive", "bargaining", "ultimatum", "demand", "leverage"],
    "SIG_RETALIATORY_THREAT": ["retaliation", "retaliatory", "counterstrike", "response", "revenge"],
    "SIG_DETERRENCE_SIGNALING": ["deterrence", "signaling", "show of force", "warning", "red line"],
    "SIG_ECON_PRESSURE": ["economic pressure", "sanctions", "trade war", "tariff", "financial"],
    "SIG_ECONOMIC_PRESSURE": ["economic", "pressure", "sanctions", "embargo", "trade"],
    "SIG_ECO_PRESSURE_HIGH": ["severe sanctions", "economic crisis", "currency collapse", "hyperinflation"],
    "SIG_ECO_SANCTIONS_ACTIVE": ["sanctions", "ofac", "sanctions regime", "asset freeze"],
    "SIG_SANCTIONS_ACTIVE": ["sanctions", "sanctioned", "restricted", "blacklist"],
    "SIG_INTERNAL_INSTABILITY": ["protest", "unrest", "instability", "riot", "civil unrest"],
    "SIG_DOM_INTERNAL_INSTABILITY": ["domestic", "instability", "protest", "regime"],
    "SIG_DECEPTION_ACTIVITY": ["deception", "disinformation", "propaganda", "false flag"],
    "SIG_MARITIME_VIOLATION": ["maritime", "territorial waters", "naval incursion", "eez violation"],
    "SIG_SOVEREIGNTY_BREACH": ["sovereignty", "airspace violation", "border incursion", "territorial"],
}


def _extract_doc_text(doc: Any) -> str:
    """Extract searchable text from a document object."""
    if isinstance(doc, dict):
        parts = []
        for key in ("content", "text", "snippet", "excerpt", "provenance_summary",
                     "title", "description", "summary"):
            val = doc.get(key, "")
            if val:
                parts.append(str(val))
        return " ".join(parts).lower()
    if isinstance(doc, str):
        return doc.lower()
    # Object with attributes
    parts = []
    for attr in ("content", "text", "snippet", "excerpt", "page_content"):
        val = getattr(doc, attr, None)
        if val:
            parts.append(str(val))
    return " ".join(parts).lower()


def compute_document_support(
    signal: str,
    retrieved_docs: List[Any],
) -> float:
    """
    Evidence-support multiplier for a single signal.

    **FIREWALL (installed 2026-03-02):**
    Always returns 1.0 — RAG documents must NOT modulate signal
    confidence.  Legal evidence is for *interpretation* (Part B),
    not for *perception* (Part A / SRE).  This ensures clean
    separation of cognition and explanation.

    See ``_compute_document_support_legacy()`` for the original logic.
    """
    return 1.0


def _compute_document_support_legacy(
    signal: str,
    retrieved_docs: List[Any],
) -> float:
    """
    Original evidence-support multiplier (preserved for reference).

    Returns 0.85 (no support), 1.10 (single match), 1.25 (multi match).
    """
    keywords = _SIGNAL_KEYWORDS.get(signal.upper(), [])
    if not keywords or not retrieved_docs:
        return 1.0

    matches = 0
    for doc in retrieved_docs:
        doc_text = _extract_doc_text(doc)
        if not doc_text:
            continue
        hit = any(kw.lower() in doc_text for kw in keywords)
        if hit:
            matches += 1

    if matches == 0:
        return 0.85
    if matches == 1:
        return 1.10
    return 1.25


def compute_all_document_support(
    signals: List[str],
    retrieved_docs: List[Any],
) -> Dict[str, float]:
    """
    Compute evidence support multipliers for all signals at once.

    **FIREWALL:** Always returns 1.0 for every signal.

    Returns
    -------
    Dict[str, float]
        Signal → 1.0 (neutral).
    """
    return {sig: 1.0 for sig in signals}


def compute_document_confidence(
    signals: List[str],
    retrieved_docs: List[Any],
) -> float:
    """
    Aggregate document support into a single document_confidence score.

    **Post-hoc reporting metric only** — this feeds the ``doc_conf``
    term in ``weighted_confidence`` (15% weight) which measures
    epistemic evidence quality.  It does NOT feed back into signal
    projection or SRE risk level.

    Uses the legacy matching logic since this is purely a confidence
    quality indicator, not a signal modulator.

    Returns mean evidence support across all projected signals,
    rescaled to [0, 1] where 1.0 = all signals have strong doc support.
    """
    if not signals or not retrieved_docs:
        return 0.0

    multipliers = {}
    for sig in signals:
        multipliers[sig] = _compute_document_support_legacy(sig, retrieved_docs)
    if not multipliers:
        return 0.0

    # Rescale: 0.85 → 0.0, 1.25 → 1.0
    raw_values = list(multipliers.values())
    rescaled = [max(0.0, min(1.0, (v - 0.85) / 0.40)) for v in raw_values]
    return sum(rescaled) / len(rescaled)
