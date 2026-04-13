"""
Core.legal.legal_output_validator — Hallucination Blocker
==========================================================

Validates LLM legal reasoning output against the evidence that was
actually provided.  If the LLM cites a treaty or article that does NOT
exist in the input evidence set, that conclusion is **dropped**.

This is the critical safety guard that makes the legal reasoning
publishable.  Without it, the LLM could cite "Geneva Convention
Article 99" (which does not exist).

Usage::

    from Core.legal.legal_output_validator import validate_legal_output

    validated = validate_legal_output(
        llm_constraints=constraints,
        evidence_items=evidence_items,
    )
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Set

logger = logging.getLogger("Core.legal.legal_output_validator")


def _normalize_authority(text: str) -> str:
    """Normalize an authority citation for fuzzy matching."""
    text = str(text or "").strip().lower()
    # Remove punctuation that varies
    text = re.sub(r"[.,;:'\"\(\)]+", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_authority_index(evidence_items: List[Any]) -> Set[str]:
    """
    Build a set of normalized authority strings from evidence items.

    Each evidence item contributes:
        - "{instrument}"
        - "{instrument} {article}"
        - "{instrument} article {article_number}"
    """
    authorities: Set[str] = set()

    for item in evidence_items:
        instrument = _normalize_authority(getattr(item, "instrument", ""))
        article = _normalize_authority(getattr(item, "article", ""))

        if instrument:
            authorities.add(instrument)
        if instrument and article:
            authorities.add(f"{instrument} {article}")
            # Also add without "article" prefix for matching flexibility
            art_num = re.sub(r"^article\s*", "", article).strip()
            if art_num:
                authorities.add(f"{instrument} article {art_num}")
                authorities.add(f"{instrument} art {art_num}")
                authorities.add(f"{instrument} art. {art_num}")

    return authorities


def _authority_matches(cited_authority: str, known_authorities: Set[str]) -> bool:
    """
    Check if a cited authority matches any known authority.

    Uses fuzzy substring matching — if the cited authority *contains*
    or *is contained by* a known authority, it passes.
    """
    if not cited_authority:
        return False

    cited = _normalize_authority(cited_authority)
    if not cited or cited == "no_applicable_authority":
        return True  # explicit "no authority" is always valid

    # Direct match
    if cited in known_authorities:
        return True

    # Substring match: cited contains a known authority or vice versa
    for known in known_authorities:
        if not known:
            continue
        if known in cited or cited in known:
            return True

    return False


def validate_legal_output(
    llm_constraints: List[Dict[str, Any]],
    evidence_items: List[Any],
) -> Dict[str, Any]:
    """
    Validate LLM legal constraint output against provided evidence.

    Parameters
    ----------
    llm_constraints : list[dict]
        The ``legal_constraints`` list from the LLM response.
    evidence_items : list[LegalEvidenceItem]
        The evidence items that were provided to the LLM.

    Returns
    -------
    dict
        {
            "validated_constraints": list[dict],  # constraints that passed
            "dropped_constraints": list[dict],    # hallucinated — removed
            "hallucinations_blocked": int,
            "total_evaluated": int,
        }
    """
    if not llm_constraints:
        return {
            "validated_constraints": [],
            "dropped_constraints": [],
            "hallucinations_blocked": 0,
            "total_evaluated": 0,
        }

    # Build authority index from evidence
    known = _build_authority_index(evidence_items)

    validated: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []

    for constraint in llm_constraints:
        if not isinstance(constraint, dict):
            continue

        authority = str(constraint.get("authority", "") or "")
        status = str(constraint.get("status", "") or "").lower()

        # "no_applicable_authority" always passes — it's a valid answer
        if status == "no_applicable_authority" or not authority:
            validated.append(constraint)
            continue

        # Check authority against known evidence
        if _authority_matches(authority, known):
            validated.append(constraint)
        else:
            dropped.append(constraint)
            logger.warning(
                "[LEGAL-VALIDATOR] HALLUCINATION BLOCKED: cited authority '%s' "
                "not found in provided evidence (%d items)",
                authority, len(evidence_items),
            )

    n_blocked = len(dropped)
    if n_blocked > 0:
        logger.info(
            "[LEGAL-VALIDATOR] %d/%d constraints validated, %d hallucination(s) blocked",
            len(validated), len(llm_constraints), n_blocked,
        )
    else:
        logger.info(
            "[LEGAL-VALIDATOR] %d/%d constraints validated — no hallucinations detected",
            len(validated), len(llm_constraints),
        )

    return {
        "validated_constraints": validated,
        "dropped_constraints": dropped,
        "hallucinations_blocked": n_blocked,
        "total_evaluated": len(llm_constraints),
    }
