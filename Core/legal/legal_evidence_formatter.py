"""
Core.legal.legal_evidence_formatter — Brain 2: Chunk → Structured Evidence
============================================================================

Converts raw RAG retrieval results (dicts with article_text, treaty_name,
etc.) into structured ``LegalEvidenceItem`` objects that the LLM legal
reasoner can consume.

Why this exists:
    Raw chunks are paragraphs.  Paragraphs make LLMs *interpret*.
    Structured evidence makes LLMs *reason*.

Each evidence item carries:
    instrument, article, actors_bound, legal_effect, excerpt,
    binding, legal_status, domain

No LLM calls — purely deterministic extraction using regex heuristics
and treaty_metadata.json.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("Core.legal.legal_evidence_formatter")


# ═══════════════════════════════════════════════════════════════════════
# DATA CLASS
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class LegalEvidenceItem:
    """One structured piece of legal evidence."""
    instrument: str              # e.g. "UN Charter"
    article: str                 # e.g. "Article 2(4)"
    actors_bound: List[str]      # e.g. ["all_states"] or ["IRN", "USA"]
    legal_effect: str            # e.g. "prohibits use of force"
    excerpt: str                 # cleaned text (≤400 chars)
    binding: bool = True
    legal_status: str = "active" # active / suspended / expired / unknown
    domain: str = ""             # use_of_force, nuclear, etc.
    confidence: float = 0.5
    signal: str = ""             # which signal triggered this retrieval

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_prompt_text(self) -> str:
        """Format for injection into LLM prompt."""
        status_tag = f" [{self.legal_status.upper()}]" if self.legal_status != "active" else ""
        binding_tag = "BINDING" if self.binding else "NON-BINDING"
        return (
            f"INSTRUMENT: {self.instrument} — {self.article}{status_tag}\n"
            f"ACTORS BOUND: {', '.join(self.actors_bound)}\n"
            f"BINDING: {binding_tag}\n"
            f"LEGAL EFFECT: {self.legal_effect}\n"
            f"EXCERPT: {self.excerpt}\n"
            f"DOMAIN: {self.domain}\n"
            f"RELEVANCE: {self.confidence:.0%}"
        )


# ═══════════════════════════════════════════════════════════════════════
# LEGAL EFFECT HEURISTICS
# ═══════════════════════════════════════════════════════════════════════

_PROHIBIT_RE = re.compile(
    r"\b(?:prohibit|forbid|shall\s+not|must\s+not|refrain\s+from|"
    r"ban(?:s|ned)?|unlawful|illegal|impermissible)\b",
    re.IGNORECASE,
)

_PERMIT_RE = re.compile(
    r"\b(?:permit(?:s|ted)?|allow(?:s|ed)?|has\s+the\s+right|"
    r"may\s+(?:use|take|exercise)|lawful|entitled\s+to|"
    r"nothing.*shall\s+impair)\b",
    re.IGNORECASE,
)

_REQUIRE_RE = re.compile(
    r"\b(?:shall|must|obligat(?:ed|ion)|require(?:s|d)?|"
    r"duty\s+to|bound\s+to|undertake(?:s)?)\b",
    re.IGNORECASE,
)

_CONDITION_RE = re.compile(
    r"\b(?:if|unless|except|provided\s+that|subject\s+to|"
    r"in\s+the\s+event|conditional(?:ly)?|only\s+when|"
    r"armed\s+attack|authorization|approval)\b",
    re.IGNORECASE,
)


def _extract_legal_effect(text: str) -> str:
    """Heuristic extraction of legal effect from chunk text."""
    if not text:
        return "unclassified"

    # Check first 500 chars for strongest signal
    sample = text[:500]

    has_prohibit = bool(_PROHIBIT_RE.search(sample))
    has_permit = bool(_PERMIT_RE.search(sample))
    has_require = bool(_REQUIRE_RE.search(sample))
    has_condition = bool(_CONDITION_RE.search(sample))

    if has_prohibit and has_condition:
        return "conditionally_prohibits"
    if has_prohibit:
        return "prohibits"
    if has_permit and has_condition:
        return "conditionally_permits"
    if has_permit:
        return "permits"
    if has_require and has_condition:
        return "conditionally_requires"
    if has_require:
        return "requires"
    if has_condition:
        return "conditional"
    return "states"


# ═══════════════════════════════════════════════════════════════════════
# TREATY METADATA LOOKUP
# ═══════════════════════════════════════════════════════════════════════

_TREATY_METADATA: Dict[str, Any] = {}
_METADATA_LOADED = False


def _load_treaty_metadata() -> Dict[str, Any]:
    global _TREATY_METADATA, _METADATA_LOADED
    if _METADATA_LOADED:
        return _TREATY_METADATA
    _METADATA_LOADED = True
    try:
        meta_path = Path(__file__).resolve().parents[2] / "legal_memory" / "treaty_metadata.json"
        if not meta_path.exists():
            from project_root import PROJECT_ROOT
            meta_path = PROJECT_ROOT / "legal_memory" / "treaty_metadata.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for treaty in data.get("treaties", []):
                tid = treaty.get("id", "")
                if tid:
                    _TREATY_METADATA[tid.lower()] = treaty
                short = treaty.get("short_name", "").lower()
                if short:
                    _TREATY_METADATA[short.lower()] = treaty
                name = treaty.get("name", "").lower()
                if name:
                    _TREATY_METADATA[name.lower()] = treaty
    except Exception as e:
        logger.debug("[FORMATTER] Failed to load treaty metadata: %s", e)
    return _TREATY_METADATA


def _lookup_treaty(treaty_name: str) -> Optional[Dict[str, Any]]:
    """Fuzzy lookup in treaty_metadata.json."""
    metadata = _load_treaty_metadata()
    if not metadata or not treaty_name:
        return None

    key = treaty_name.strip().lower()
    # Direct match
    if key in metadata:
        return metadata[key]
    # Partial match
    for mk, mv in metadata.items():
        if key in mk or mk in key:
            return mv
    return None


def _get_actors_bound(treaty_info: Optional[Dict], fallback_country: str = "") -> List[str]:
    """Extract the actors bound by a treaty."""
    if treaty_info:
        signatories = treaty_info.get("signatories", [])
        if "ALL_UN_MEMBERS" in signatories:
            return ["all_states"]
        if signatories:
            return list(signatories)

    # Fallback for constitutions — bound to the country itself
    if fallback_country:
        return [fallback_country.upper()]
    return ["unknown"]


def _is_binding(treaty_info: Optional[Dict]) -> bool:
    """Determine if the treaty is legally binding."""
    if treaty_info is None:
        return True  # Assume binding unless we know otherwise
    status = treaty_info.get("status", "active").lower()
    return status in ("active", "signed_not_ratified")


# ═══════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════

def format_legal_evidence(
    raw_results: List[Dict[str, Any]],
) -> List[LegalEvidenceItem]:
    """
    Convert raw RAG results into structured LegalEvidenceItem objects.

    Parameters
    ----------
    raw_results : list[dict]
        RAG evidence records from ``retrieve_legal_evidence()``
        (post treaty-validator filtering).

    Returns
    -------
    list[LegalEvidenceItem]
        Structured evidence items ready for LLM consumption.
    """
    items: List[LegalEvidenceItem] = []

    for rec in raw_results:
        if not isinstance(rec, dict):
            continue

        treaty_name = str(rec.get("treaty_name", "") or "").strip()
        article_number = str(rec.get("article_number", "") or "").strip()
        domain = str(rec.get("domain", "") or "").strip()
        country = str(rec.get("country", "") or "").strip()
        text = str(rec.get("article_text", rec.get("excerpt", "")) or "").strip()
        signal = str(rec.get("signal", "") or "").strip()
        legal_status = str(rec.get("legal_status", "active") or "active").strip()
        confidence = float(rec.get("relevance", rec.get("confidence", 0.5)) or 0.5)

        # Clean the excerpt
        excerpt = text[:400].strip()
        if text and len(text) > 400:
            excerpt += "..."

        # Lookup treaty metadata for actors_bound and binding status
        treaty_info = _lookup_treaty(treaty_name)

        # Build the instrument display name
        instrument = treaty_name or rec.get("source", "Unknown")

        # Build article display name
        article = f"Article {article_number}" if article_number else ""

        # Extract legal effect from text
        legal_effect = _extract_legal_effect(text)

        items.append(LegalEvidenceItem(
            instrument=instrument,
            article=article,
            actors_bound=_get_actors_bound(treaty_info, fallback_country=country),
            legal_effect=legal_effect,
            excerpt=excerpt,
            binding=_is_binding(treaty_info),
            legal_status=legal_status,
            domain=domain,
            confidence=confidence,
            signal=signal,
        ))

    logger.info(
        "[FORMATTER] Formatted %d raw results → %d evidence items",
        len(raw_results), len(items),
    )
    return items


def evidence_to_prompt_block(items: List[LegalEvidenceItem]) -> str:
    """
    Render all evidence items as a single text block for LLM injection.
    """
    if not items:
        return "No legal evidence available."

    lines = []
    for i, item in enumerate(items, 1):
        lines.append(f"--- Evidence {i} ---")
        lines.append(item.to_prompt_text())
        lines.append("")

    return "\n".join(lines)
