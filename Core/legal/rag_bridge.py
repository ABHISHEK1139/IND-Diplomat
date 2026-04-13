"""
Core.legal.rag_bridge — RAG Retrieval → Signal Converter
==========================================================
Queries the ChromaDB ``legal_articles`` collection for documents
relevant to observed escalation signals, then converts retrieved
articles into **legal evidence records** that feed into:

    • ``state_context.signal_evidence``       (grounding)
    • ``state_context.evidence.signal_provenance``  (audit trail)
    • ``document_confidence``                  (was always 0.00 without this)

This module is the **librarian** — it gives the council access to
the law library that was built by ``build_legal_index.py``.

Design constraints:
    • No LLM calls — purely embedding-similarity retrieval
    • Tolerates missing ChromaDB (graceful degrade to empty)
    • Idempotent — safe to call multiple times per assessment
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("Core.legal.rag_bridge")

# ── Signal → query mapping ───────────────────────────────────────
# Each observed signal maps to one or more natural-language queries
# that will be sent to the legal article vector store.
#
# The goal: retrieve treaty text that *explains the legal context*
# of a detected escalation signal.

SIGNAL_QUERY_MAP: Dict[str, List[str]] = {
    # Military / sovereignty
    "SIG_MIL_ESCALATION": [
        "use of force international law UN Charter Article 2(4)",
        "armed attack self-defense Article 51",
    ],
    "SIG_FORCE_POSTURE": [
        "military deployment sovereignty UNCLOS territorial waters",
        "force posture forward deployment international law",
    ],
    "SIG_BORDER_CLASH": [
        "border dispute sovereignty territorial integrity",
    ],
    "SIG_TERRITORIAL_INCURSION": [
        "territorial sovereignty violation aggression",
    ],
    "SIG_FORCE_CONCENTRATION": [
        "military buildup threat of force international law",
    ],

    # Naval / maritime
    "SIG_CHOKEPOINT_CONTROL": [
        "strait passage UNCLOS transit innocent passage",
    ],
    "SIG_BLOCKADE": [
        "naval blockade act of war UNCLOS freedom of navigation",
        "blockade international humanitarian law",
    ],
    "SIG_LOGISTICS_SURGE": [
        "military logistics deployment rules of engagement",
    ],
    "SIG_LOGISTICS_PREP": [
        "military logistics preparation mobilization law",
    ],

    # Economic / sanctions
    "SIG_SANCTIONS_ACTIVE": [
        "economic sanctions legality WTO international law",
        "unilateral sanctions coercion countermeasures",
    ],
    "SIG_ECO_SANCTIONS_ACTIVE": [
        "economic sanctions enforcement UN Security Council",
    ],
    "SIG_ECONOMIC_PRESSURE": [
        "economic coercion international law sovereignty",
    ],

    # Diplomatic / treaty
    "SIG_NEGOTIATION_BREAKDOWN": [
        "treaty obligation breach Vienna Convention pacta sunt servanda",
    ],
    "SIG_DIP_BREAK": [
        "diplomatic relations severance Vienna Convention consular",
    ],
    "SIG_TREATY_BREAK": [
        "treaty violation material breach consequences",
    ],
    "SIG_DIP_CHANNEL_CLOSURE": [
        "diplomatic channels closure mediation obligation",
    ],
    "SIG_DIP_HOSTILITY": [
        "hostile diplomatic actions declaration persona non grata",
    ],

    # WMD / proliferation
    "SIG_WMD_RISK": [
        "weapons of mass destruction nonproliferation treaty NPT",
        "chemical weapons convention biological weapons",
    ],

    # Cyber
    "SIG_CYBER_ACTIVITY": [
        "cyber attack sovereignty international law Tallinn Manual",
        "cyber warfare rules of engagement",
    ],
    "SIG_CYBER_PREPARATION": [
        "cyber operations state responsibility attribution",
    ],

    # Internal stability
    "SIG_INTERNAL_INSTABILITY": [
        "internal conflict human rights obligations R2P",
    ],

    # Alliance
    "SIG_ALLIANCE_ACTIVATION": [
        "collective defense alliance treaty NATO Article 5",
    ],
    "SIG_ALLIANCE_SHIFT": [
        "alliance realignment treaty obligations mutual defense",
    ],

    # Coercive bargaining
    "SIG_COERCIVE_BARGAINING": [
        "coercive diplomacy ultimatum international law",
    ],
}

# Minimum similarity score (1 - distance) to consider a result relevant
RELEVANCE_THRESHOLD = 0.30


def _try_import_indexer():
    """Lazy import to avoid loading SentenceTransformer at module import time."""
    import sys
    from pathlib import Path
    # Ensure project root is on sys.path
    _root = str(Path(__file__).resolve().parent.parent.parent)
    if _root not in sys.path:
        sys.path.insert(0, _root)

    attempts = [
        lambda: __import__('Core.legal.legal_indexer', fromlist=['query_legal_articles']).query_legal_articles,
        lambda: __import__('core.legal.legal_indexer', fromlist=['query_legal_articles']).query_legal_articles,
    ]
    for attempt in attempts:
        try:
            return attempt()
        except Exception:  # noqa: BLE001
            continue
    logger.warning("[RAG] Cannot import legal_indexer — RAG disabled")
    return None


def retrieve_legal_evidence(
    observed_signals: Set[str],
    *,
    n_results: int = 3,
    relevance_threshold: float = RELEVANCE_THRESHOLD,
    country_code: str = "",
    target_country: str = "",
) -> List[Dict[str, Any]]:
    """
    For each observed signal that has a RAG query mapping, retrieve the
    most relevant legal articles from ChromaDB.

    Parameters
    ----------
    country_code : str, optional
        ISO-3 country code of the subject actor.  When provided,
        constitutions from unrelated countries are soft-downranked
        (50% relevance penalty).  International frameworks (UN Charter,
        Geneva Conventions, WTO, etc.) are never downranked.
    target_country : str, optional
        ISO-3 country code of the target actor.  Passed to the
        treaty validator for jurisdiction filtering.

    Returns a list of evidence records::

        [
            {
                "signal": "SIG_MIL_ESCALATION",
                "query": "use of force ...",
                "article_text": "Article 2(4) ...",
                "source": "global/un_charter.pdf",
                "root": "global",
                "distance": 0.31,
                "relevance": 0.69,
            },
            ...
        ]
    """
    query_fn = _try_import_indexer()
    if query_fn is None:
        return []

    results: List[Dict[str, Any]] = []
    seen_articles: Set[str] = set()  # dedup by article_text prefix

    # ── Metadata-aware retrieval strategy ────────────────────────
    # For each signal, determine the appropriate ChromaDB `where`
    # filter so that constitutions from irrelevant countries never
    # enter the result set in the first place.
    #
    # Strategy:
    #   - Signals about international law → filter: root == "global"
    #   - Signals about domestic law → filter: country matches actor
    #   - Signals about trade → filter: root == "trade"
    #   - Default: no filter (maximize recall, let validator clean up)
    _INTL_SIGNALS = {
        "SIG_MIL_ESCALATION", "SIG_WMD_RISK", "SIG_ILLEGAL_COERCION",
        "SIG_SOVEREIGNTY_BREACH", "SIG_BLOCKADE", "SIG_CHOKEPOINT_CONTROL",
        "SIG_MARITIME_VIOLATION", "SIG_ALLIANCE_ACTIVATION", "SIG_ALLIANCE_SHIFT",
        "SIG_CYBER_ACTIVITY", "SIG_CYBER_PREPARATION", "SIG_NUCLEAR_ACTIVITY",
        "SIG_FORCE_POSTURE", "SIG_BORDER_CLASH", "SIG_TERRITORIAL_INCURSION",
        "SIG_COERCIVE_BARGAINING", "SIG_RETALIATORY_THREAT",
        "SIG_DETERRENCE_SIGNALING", "SIG_DIP_HOSTILITY",
        "SIG_NEGOTIATION_BREAKDOWN", "SIG_DIP_BREAK", "SIG_TREATY_BREAK",
    }
    _TRADE_SIGNALS = {
        "SIG_SANCTIONS_ACTIVE", "SIG_ECO_SANCTIONS_ACTIVE",
        "SIG_ECONOMIC_PRESSURE",
    }

    for signal in sorted(observed_signals):
        queries = SIGNAL_QUERY_MAP.get(signal.strip().upper(), [])
        if not queries:
            continue

        # Determine metadata filter for this signal
        sig_upper = signal.strip().upper()
        where_filter: Optional[Dict] = None
        if sig_upper in _INTL_SIGNALS:
            where_filter = {"root": "global"}
        elif sig_upper in _TRADE_SIGNALS:
            # Trade signals: try trade first, then global
            where_filter = {"root": "trade"}

        for query_text in queries:
            try:
                # First pass: with metadata filter (precise)
                raw = query_fn(
                    query=query_text, n_results=n_results,
                    where=where_filter,
                )
                documents = (raw.get("documents") or [[]])[0]

                # If metadata filter returns too few results, retry without filter
                if len(documents) < 2 and where_filter:
                    raw_fallback = query_fn(
                        query=query_text, n_results=n_results,
                    )
                    fb_docs = (raw_fallback.get("documents") or [[]])[0]
                    if len(fb_docs) > len(documents):
                        raw = raw_fallback
                        documents = fb_docs
            except Exception as exc:
                logger.debug("[RAG] Query failed for '%s': %s", query_text, exc)
                continue

            metadatas = (raw.get("metadatas") or [[]])[0]
            distances = (raw.get("distances") or [[]])[0]

            for doc_text, meta, dist in zip(documents, metadatas, distances):
                if not doc_text:
                    continue

                # ChromaDB cosine distance: 0 = identical, 2 = opposite
                relevance = 1.0 - (dist / 2.0)
                if relevance < relevance_threshold:
                    continue

                # Dedup: skip if we already retrieved very similar text
                dedup_key = doc_text[:200].strip()
                if dedup_key in seen_articles:
                    continue
                seen_articles.add(dedup_key)

                results.append({
                    "signal": signal,
                    "query": query_text,
                    "article_text": doc_text[:2000],  # cap for memory
                    "source": meta.get("source", "unknown"),
                    "root": meta.get("root", "unknown"),
                    "distance": round(dist, 4),
                    "relevance": round(relevance, 4),
                    # Rich metadata from structure-aware chunking
                    "treaty_name": meta.get("treaty_name", ""),
                    "article_number": meta.get("article_number", ""),
                    "domain": meta.get("domain", ""),
                    "year": meta.get("year", ""),
                    "heading": meta.get("heading", ""),
                    "country": meta.get("country", ""),
                    "chunk_type": meta.get("chunk_type", ""),
                })

    logger.info(
        "[RAG] Retrieved %d legal article(s) for %d signal(s)",
        len(results), len(observed_signals),
    )

    # ── Actor-relevance filter ───────────────────────────────────
    # Downrank constitutions from countries unrelated to the assessment.
    # International frameworks (global, un_charter, geneva, wto, etc.)
    # are never penalised.
    _INTL_ROOTS = {"global", "un_charter", "geneva", "wto", "icc", "icj", ""}
    if country_code and country_code != "UNKNOWN":
        _cc_lower = country_code.strip().lower()
        filtered = []
        for rec in results:
            doc_country = str(rec.get("country", "") or "").strip().lower()
            doc_root = str(rec.get("root", "") or "").strip().lower()
            doc_domain = str(rec.get("domain", "") or "").strip().lower()
            # International frameworks pass through unpenalised
            if doc_root in _INTL_ROOTS or doc_domain in ("war", "organization", "trade"):
                filtered.append(rec)
                continue
            # Country-specific: pass if it matches the subject
            if doc_country and _cc_lower not in doc_country and doc_country not in _cc_lower:
                # Soft downrank: halve relevance
                adjusted = rec["relevance"] * 0.5
                if adjusted >= relevance_threshold:
                    rec["relevance"] = round(adjusted, 4)
                    filtered.append(rec)
                else:
                    logger.debug("[RAG] Dropped irrelevant: %s %s (country=%s, adj_rel=%.3f)",
                                 rec.get("treaty_name"), rec.get("article_number"),
                                 doc_country, adjusted)
            else:
                filtered.append(rec)
        if len(filtered) < len(results):
            logger.info("[RAG] Actor-filter: %d → %d articles (country=%s)",
                        len(results), len(filtered), country_code)
        results = filtered

    # ── Treaty Validator: jurisdiction + domain + temporal filter ─
    # Strict second pass: drops constitutions from unrelated countries
    # entirely, penalises off-topic domains, rejects pre-1900 treaties.
    try:
        from Core.legal.treaty_validator import validate_legal_relevance
        results = validate_legal_relevance(
            results,
            subject_country=country_code,
            target_country=target_country,
            active_signals=observed_signals,
        )
    except ImportError:
        logger.debug("[RAG] treaty_validator not available — skipping")
    except Exception as exc:
        logger.warning("[RAG] treaty_validator error: %s", exc)

    return results


def inject_legal_evidence_into_context(
    state_context: Any,
    evidence_records: List[Dict[str, Any]],
    *,
    assessment_date: str = "",
) -> Tuple[int, float]:
    """
    Inject RAG-retrieved legal evidence into the state context so it
    appears in provenance, signal_evidence, and document_confidence.

    Returns (articles_injected, avg_relevance).
    """
    if not evidence_records:
        return 0, 0.0

    signal_evidence = dict(getattr(state_context, "signal_evidence", {}) or {})
    provenance_map = dict(
        getattr(
            getattr(state_context, "evidence", None),
            "signal_provenance",
            {},
        ) or {}
    )

    total_relevance = 0.0
    injected = 0

    for rec in evidence_records:
        signal = rec["signal"]
        excerpt = rec["article_text"][:500]
        source_file = rec.get("source", "unknown")
        source_root = rec.get("root", "unknown")
        relevance = rec.get("relevance", 0.5)

        row = {
            "source_id": f"rag_legal::{signal}::{source_root}::{assessment_date or 'na'}",
            "source": f"RAG/{source_root}",
            "source_name": f"RAG Legal: {source_root}",
            "url": "",
            "publication_date": str(assessment_date or ""),
            "date": str(assessment_date or ""),
            "excerpt": f"[RAG] {excerpt}",
            "confidence": float(relevance),
            "reliability": float(min(relevance + 0.1, 1.0)),
            "rag_source_file": str(source_file),
            "rag_relevance": float(relevance),
            # Rich metadata for dual-track report
            "treaty_name": str(rec.get("treaty_name", "")),
            "article_number": str(rec.get("article_number", "")),
            "domain": str(rec.get("domain", "")),
            "year": str(rec.get("year", "")),
            "heading": str(rec.get("heading", "")),
            "country": str(rec.get("country", "")),
            "chunk_type": str(rec.get("chunk_type", "")),
        }

        # ── Add to signal_evidence ─────────────────────────────
        sig_rows = list(signal_evidence.get(signal, []) or [])
        sig_rows.append(dict(row))
        signal_evidence[signal] = sig_rows

        # ── Add to provenance ──────────────────────────────────
        prov_rows = list(provenance_map.get(signal, []) or [])
        prov_rows.append(dict(row))
        provenance_map[signal] = prov_rows

        total_relevance += relevance
        injected += 1

    state_context.signal_evidence = signal_evidence
    if hasattr(state_context, "evidence") and state_context.evidence is not None:
        state_context.evidence.signal_provenance = provenance_map

    avg_relevance = total_relevance / max(1, injected)

    logger.info(
        "[RAG] Injected %d legal evidence record(s), avg_relevance=%.3f",
        injected, avg_relevance,
    )
    return injected, avg_relevance
