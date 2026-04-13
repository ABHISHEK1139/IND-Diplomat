"""
Treaty Validator — Jurisdiction & Domain Relevance Filter
==========================================================

Sits *after* RAG retrieval and *before* the final report.
Ensures legal evidence is jurisdictionally and topically relevant
to the assessed conflict, eliminating nonsense citations like
"Colombia constitution for Iran assessment".

Three filter rules applied sequentially:

1. **Jurisdiction Filter**
   - International treaties pass unconditionally.
   - Domestic law (constitutions) passes only if the country matches
     the subject or target actor.  All others are *dropped*.

2. **Domain Relevance Filter**
   - Maps active signals → required legal domains.
   - Off-topic articles get a 60% relevance penalty.
   - On-topic articles get a 10% boost (capped 1.0).

3. **Temporal Validity (soft)**
   - Treaties from before 1900 are dropped.
   - Very old constitutions get a mild downrank.

Pipeline position::

    RAG retrieval  →  actor-relevance soft filter (rag_bridge)
                   →  **treaty_validator**  ← THIS MODULE
                   →  legal reasoning / briefing
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

# Roots / domains that are inherently international (never jurisdiction-gated)
_INTERNATIONAL_ROOTS: Set[str] = {
    "global", "trade", "organizations", "un_charter",
    "geneva", "wto", "icc", "icj", "",
}

_INTERNATIONAL_DOMAINS: Set[str] = {
    "war", "collective_defense", "use_of_force", "sanctions",
    "nuclear", "nonproliferation", "human_rights", "maritime",
    "organization", "trade", "humanitarian",
}

# Signal-group → relevant legal domains mapping
_SIGNAL_DOMAIN_MAP: Dict[str, Set[str]] = {
    # Military signals
    "SIG_MIL_ESCALATION":       {"war", "collective_defense", "use_of_force", "sanctions"},
    "SIG_MIL_MOBILIZATION":     {"war", "collective_defense", "use_of_force"},
    "SIG_FORCE_POSTURE":        {"war", "collective_defense", "use_of_force"},
    "SIG_LOGISTICS_PREP":       {"war", "use_of_force"},
    # Diplomatic / alliance
    "SIG_DIP_HOSTILITY":        {"collective_defense", "organization", "sanctions"},
    "SIG_DIP_HOSTILE_RHETORIC":  {"collective_defense", "organization"},
    "SIG_ALLIANCE_SHIFT":       {"collective_defense", "organization"},
    "SIG_ALLIANCE_ACTIVATION":  {"collective_defense", "organization"},
    "SIG_NEGOTIATION_BREAKDOWN": {"collective_defense", "sanctions", "organization"},
    # Economic / sanctions
    "SIG_ECON_PRESSURE":        {"sanctions", "trade"},
    "SIG_ECONOMIC_PRESSURE":    {"sanctions", "trade"},
    "SIG_ECO_PRESSURE_HIGH":    {"sanctions", "trade"},
    "SIG_ECO_SANCTIONS_ACTIVE": {"sanctions", "trade"},
    "SIG_SANCTIONS_ACTIVE":     {"sanctions", "trade"},
    # WMD / nuclear
    "SIG_WMD_RISK":             {"nuclear", "nonproliferation", "sanctions", "use_of_force"},
    "SIG_NUCLEAR_ACTIVITY":     {"nuclear", "nonproliferation"},
    # Cyber / sovereignty
    "SIG_CYBER_ACTIVITY":       {"war", "use_of_force"},
    "SIG_SOVEREIGNTY_BREACH":   {"war", "use_of_force", "maritime"},
    "SIG_MARITIME_VIOLATION":   {"maritime", "war"},
    # Domestic
    "SIG_INTERNAL_INSTABILITY":  {"human_rights"},
    "SIG_DOM_INTERNAL_INSTABILITY": {"human_rights"},
    "SIG_PUBLIC_PROTEST":        {"human_rights"},
    "SIG_ELITE_FRACTURE":       {"human_rights"},
    "SIG_MILITARY_DEFECTION":   {"human_rights", "war", "use_of_force"},
    "SIG_DECEPTION_ACTIVITY":    {"war"},
    # Coercion
    "SIG_ILLEGAL_COERCION":     {"sanctions", "use_of_force"},
    "SIG_COERCIVE_BARGAINING":  {"sanctions", "trade"},
    "SIG_RETALIATORY_THREAT":   {"war", "collective_defense", "sanctions"},
    "SIG_DETERRENCE_SIGNALING": {"war", "collective_defense"},
}

# Constitution-indicator patterns in root / source path
_CONSTITUTION_PATTERNS = re.compile(
    r"constitution|domestic|countries", re.IGNORECASE,
)

# Minimum relevance to survive filtering
_MIN_RELEVANCE = 0.15


# ═══════════════════════════════════════════════════════════════════════
# TREATY METADATA — signatory-based applicability check
# ═══════════════════════════════════════════════════════════════════════

_TREATY_METADATA: Dict[str, Any] = {}
_METADATA_LOADED = False


def _load_treaty_metadata() -> Dict[str, Any]:
    """Load treaty_metadata.json once (lazy singleton)."""
    global _TREATY_METADATA, _METADATA_LOADED
    if _METADATA_LOADED:
        return _TREATY_METADATA
    _METADATA_LOADED = True
    try:
        import json
        from pathlib import Path
        meta_path = Path(__file__).resolve().parents[2] / "legal_memory" / "treaty_metadata.json"
        if not meta_path.exists():
            # Also try project root
            from project_root import PROJECT_ROOT
            meta_path = PROJECT_ROOT / "legal_memory" / "treaty_metadata.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Index by treaty id AND by short_name (lowered) for lookup
            for treaty in data.get("treaties", []):
                tid = treaty.get("id", "")
                if tid:
                    _TREATY_METADATA[tid] = treaty
                short = treaty.get("short_name", "").lower()
                if short:
                    _TREATY_METADATA[short] = treaty
                name = treaty.get("name", "").lower()
                if name:
                    _TREATY_METADATA[name] = treaty
            logger.info(
                "[TREATY-VALIDATOR] Loaded %d treaties from %s",
                len(data.get("treaties", [])), meta_path,
            )
        else:
            logger.debug("[TREATY-VALIDATOR] No treaty_metadata.json found")
    except Exception as e:
        logger.debug("[TREATY-VALIDATOR] Failed to load treaty metadata: %s", e)
    return _TREATY_METADATA


def _is_signatory(treaty_name: str, actor_iso: str) -> bool:
    """
    Check if an actor is a signatory of a treaty.

    Returns True if:
    - Treaty metadata not loaded (fail-open)
    - Treaty has ALL_UN_MEMBERS in signatories
    - Actor ISO code appears in signatories list
    """
    metadata = _load_treaty_metadata()
    if not metadata:
        return True  # No metadata → fail open (don't block)

    # Try lookup by treaty_name (case-insensitive)
    treaty = metadata.get(treaty_name.lower())
    if treaty is None:
        # Try partial match
        name_lower = treaty_name.lower()
        for key, val in metadata.items():
            if name_lower in key or key in name_lower:
                treaty = val
                break

    if treaty is None:
        return True  # Unknown treaty → fail open

    signatories = treaty.get("signatories", [])
    if "ALL_UN_MEMBERS" in signatories:
        return True

    # Check if actor is in signatories
    actor_upper = actor_iso.strip().upper()
    return actor_upper in [s.upper() for s in signatories]


def _is_treaty_active(treaty_name: str) -> bool:
    """Check if a treaty is currently active."""
    metadata = _load_treaty_metadata()
    if not metadata:
        return True  # No metadata → assume active

    treaty = metadata.get(treaty_name.lower())
    if treaty is None:
        name_lower = treaty_name.lower()
        for key, val in metadata.items():
            if name_lower in key or key in name_lower:
                treaty = val
                break

    if treaty is None:
        return True  # Unknown → assume active

    status = treaty.get("status", "active").lower()
    return status in ("active", "signed_not_ratified")


# ═══════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════

def validate_legal_relevance(
    results: List[Dict[str, Any]],
    subject_country: str = "",
    target_country: str = "",
    active_signals: Set[str] | None = None,
) -> List[Dict[str, Any]]:
    """
    Apply jurisdiction + domain + temporal filters to RAG results.

    Parameters
    ----------
    results : list[dict]
        RAG evidence records (from ``retrieve_legal_evidence``).
    subject_country : str
        ISO name or code of the subject actor (e.g. "iran", "IRN").
    target_country : str
        ISO name or code of the target actor (e.g. "usa", "USA").
    active_signals : set[str], optional
        Currently active signal codes.  Used for domain relevance
        matching.  If None, domain filtering is skipped.

    Returns
    -------
    list[dict]
        Filtered & re-scored results.
    """
    if not results:
        return results

    # Normalise actor names for matching
    _actors = set()
    for actor in (subject_country, target_country):
        if actor and actor.upper() != "UNKNOWN":
            _actors.add(actor.strip().lower())

    # Build the union of relevant domains from active signals
    _relevant_domains: Set[str] = set()
    if active_signals:
        for sig in active_signals:
            _relevant_domains |= _SIGNAL_DOMAIN_MAP.get(
                sig.strip().upper(), set()
            )

    validated: List[Dict[str, Any]] = []
    dropped_jurisdiction = 0
    dropped_relevance = 0

    dropped_source_type = 0

    for rec in results:
        doc_root = str(rec.get("root", "") or "").strip().lower()
        doc_domain = str(rec.get("domain", "") or "").strip().lower()
        doc_country = str(rec.get("country", "") or "").strip().lower()
        doc_source = str(rec.get("source", "") or "").strip().lower()
        doc_year = str(rec.get("year", "") or "").strip()

        # ── Rule 0: Source Type Filter ───────────────────────────
        # Only allow primary treaty text.  Academic papers, blogs,
        # and news articles that MENTION treaties are not legal
        # evidence — they are commentary.
        doc_chunk_source = str(rec.get("chunk_source", "") or "").strip().lower()
        if doc_chunk_source and doc_chunk_source not in (
            "treaty_corpus", "legal_corpus", "primary_text",
            "constitution", "statute", "convention", "",
        ):
            dropped_source_type += 1
            logger.debug(
                "[TREATY-VALIDATOR] Source-type drop: %s %s "
                "(chunk_source=%s, not primary legal text)",
                rec.get("treaty_name"), rec.get("article_number"),
                doc_chunk_source,
            )
            continue  # HARD DROP

        # ── Rule 1: Jurisdiction Filter ──────────────────────────
        is_international = (
            doc_root in _INTERNATIONAL_ROOTS
            or doc_domain in _INTERNATIONAL_DOMAINS
        )
        is_constitution = bool(
            _CONSTITUTION_PATTERNS.search(doc_root)
            or _CONSTITUTION_PATTERNS.search(doc_source)
            or doc_domain in ("constitutional_law", "constitutional")
        )

        if not is_international and is_constitution:
            # Domestic law — must match an actor
            if doc_country and not any(
                actor in doc_country or doc_country in actor
                for actor in _actors
            ):
                dropped_jurisdiction += 1
                logger.debug(
                    "[TREATY-VALIDATOR] Jurisdiction drop: %s %s "
                    "(country=%s, actors=%s)",
                    rec.get("treaty_name"), rec.get("article_number"),
                    doc_country, _actors,
                )
                continue  # HARD DROP — not downrank

        # ── Rule 2: Domain Relevance Filter ──────────────────────
        if _relevant_domains and doc_domain:
            if doc_domain in _relevant_domains:
                # On-topic: 10% boost
                rec["relevance"] = round(
                    min(1.0, rec.get("relevance", 0.5) * 1.10), 4
                )
            elif is_international:
                # International but off-topic: no penalty but no boost
                pass
            else:
                # Off-topic domestic/misc: 60% penalty
                rec["relevance"] = round(
                    rec.get("relevance", 0.5) * 0.40, 4
                )
                if rec["relevance"] < _MIN_RELEVANCE:
                    dropped_relevance += 1
                    logger.debug(
                        "[TREATY-VALIDATOR] Domain drop: %s %s "
                        "(domain=%s not in %s)",
                        rec.get("treaty_name"), rec.get("article_number"),
                        doc_domain, _relevant_domains,
                    )
                    continue

        # ── Rule 2.5: Signatory Applicability ────────────────────
        # If we have treaty metadata, check if either the subject or
        # target actor is actually bound by this treaty.
        doc_treaty = str(rec.get("treaty_name", "") or "").strip()
        if doc_treaty and _actors and not is_international:
            # Check if at least one actor is a signatory
            any_signatory = any(
                _is_signatory(doc_treaty, actor.upper())
                for actor in _actors
            )
            if not any_signatory:
                logger.debug(
                    "[TREATY-VALIDATOR] Signatory drop: %s %s "
                    "(treaty=%s, actors=%s not signatories)",
                    rec.get("treaty_name"), rec.get("article_number"),
                    doc_treaty, _actors,
                )
                continue  # Neither actor is bound by this treaty

            # Check treaty status (active/suspended/expired)
            if not _is_treaty_active(doc_treaty):
                rec["relevance"] = round(
                    rec.get("relevance", 0.5) * 0.50, 4
                )
                logger.debug(
                    "[TREATY-VALIDATOR] Treaty not active: %s (50%% penalty)",
                    doc_treaty,
                )

        # ── Rule 3: Temporal Validity (soft) ─────────────────────
        if doc_year:
            try:
                yr = int(doc_year)
                if yr < 1900:
                    logger.debug(
                        "[TREATY-VALIDATOR] Temporal drop: %s year=%d",
                        rec.get("treaty_name"), yr,
                    )
                    continue
            except (ValueError, TypeError):
                pass

        # ── Rule 4: Legal Status Annotation ──────────────────────
        # Annotate each surviving result with its treaty's current
        # legal status. This lets Part-B say "actors are no longer
        # constrained by treaty" when a treaty is suspended/expired.
        doc_treaty = str(rec.get("treaty_name", "") or "").strip()
        if doc_treaty:
            metadata = _load_treaty_metadata()
            treaty_info = metadata.get(doc_treaty.lower())
            if treaty_info:
                rec["legal_status"] = treaty_info.get("status", "active")
            else:
                rec["legal_status"] = "active"  # assume active if unknown
        else:
            rec["legal_status"] = "unknown"

        validated.append(rec)

    if dropped_jurisdiction or dropped_relevance or dropped_source_type:
        logger.info(
            "[TREATY-VALIDATOR] %d → %d articles "
            "(source_type_drop=%d, jurisdiction_drop=%d, domain_drop=%d)",
            len(results), len(validated),
            dropped_source_type, dropped_jurisdiction, dropped_relevance,
        )

    return validated
