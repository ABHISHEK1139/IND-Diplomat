"""
PIR → MoltBot Collection Bridge
================================

This module is the ONLY point where typed PIRs touch the real world.

    PIR  →  CollectionTask  →  MoltBot  →  raw docs  →  signal_hits

Design invariants:
    1. MoltBot receives TOPICS, never the user's question.
    2. MoltBot returns raw documents; this bridge converts them to
       signal_hits — the same format investigate_and_update() expects.
    3. One PIR produces one or more signal_hits, each tied to the
       PIR's signal token so the evidence integrator can merge them.
    4. The bridge never interprets content — that's SignalProjection's
       job on the NEXT pass through the pipeline.
    5. Reliability for web-sourced evidence starts LOW (0.35) and
       can only be raised by downstream verification.

Flow:
    coordinator._run_investigation_phase()
        → investigate_and_update()
            → execute_collection_plan()   ← THIS MODULE
                → MoltBot.collect_documents()
            → evidence integration (existing code in state_provider)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from Utils.country_normalization import resolve_country_name

logger = logging.getLogger("intelligence.collection_bridge")


# =====================================================================
# Modality → Topic Keywords  (closed map — NOT free-text generation)
# =====================================================================
# These are domain-specific search TOPICS that MoltBot combines with
# the country to form a web query.  They are NOT the user's question.
#
# Example:  PIR(signal=SIG_MIL_ESCALATION, collection=SIPRI_ARMS, country=Iran)
#           → topic = "military arms transfers defense spending"
#           → MoltBot query = "Iran military arms transfers defense spending"
#
# The topic describes WHAT SENSOR DATA LOOKS LIKE on the open web,
# not what the analyst wants to know.
# =====================================================================

MODALITY_TOPIC_MAP: Dict[str, str] = {
    "IMINT":          "satellite imagery military deployment troop movement",
    "SIGINT":         "communications intercept signals intelligence",
    "OSINT_EVENTS":   "conflict events incidents ACLED GDELT armed clashes",
    "OSINT_SOCIAL":   "protests social unrest demonstrations civil disorder",
    "DIPLOMATIC_RPT": "diplomatic relations embassy summit UN resolution",
    "TRADE_FLOW":     "trade sanctions economic pressure import export tariff",
    "LEGAL_CORPUS":   "treaty UNSCR resolution international law agreement",
    "SIPRI_ARMS":     "military arms transfers defense spending SIPRI weapons",
    "HUMINT":         "intelligence source defector insider report",
    "CYBER_INTEL":    "cyber attack threat intelligence hacking APT",
    "V_DEM":          "governance regime quality democracy index V-Dem",
}

# Signal → human-readable topic fragments (supplements modality topic)
SIGNAL_TOPIC_HINT: Dict[str, str] = {
    "SIG_MIL_ESCALATION":      "military escalation buildup",
    "SIG_FORCE_POSTURE":       "force posture readiness deployment",
    "SIG_MIL_MOBILIZATION":    "troop mobilization reserve activation",
    "SIG_LOGISTICS_PREP":      "logistics preparation supply chain military",
    "SIG_LOGISTICS_SURGE":     "logistics surge supply movement",
    "SIG_CYBER_ACTIVITY":      "cyber operations attack campaign",
    "SIG_CYBER_PREPARATION":   "cyber preparation offensive capability",
    "SIG_WMD_RISK":            "WMD nuclear chemical biological weapons",
    "SIG_DECEPTION_ACTIVITY":  "deception concealment denial disinformation",
    "SIG_DIP_HOSTILITY":       "diplomatic hostility ambassador recall",
    "SIG_DIP_HOSTILE_RHETORIC": "hostile rhetoric threat statements",
    "SIG_ALLIANCE_ACTIVATION": "alliance activation mutual defense treaty",
    "SIG_ALLIANCE_SHIFT":      "alliance realignment partnership shift",
    "SIG_NEGOTIATION_BREAKDOWN": "negotiation collapse talks failed",
    "SIG_COERCIVE_PRESSURE":   "coercive pressure sanctions economic coercion",
    "SIG_COERCIVE_BARGAINING": "coercive diplomacy ultimatum pressure",
    "SIG_RETALIATORY_THREAT":  "retaliation threat counter-strike warning",
    "SIG_DETERRENCE_SIGNALING": "deterrence signaling show of force",
    "SIG_LEGAL_VIOLATION":     "legal violation treaty breach UNSCR",
    "SIG_INTERNAL_INSTABILITY": "internal instability regime fragility",
    "SIG_INTERNAL_UNREST":     "internal unrest protests crackdown",
    "SIG_DOM_INTERNAL_INSTABILITY": "domestic instability political crisis",
    "SIG_ECO_SANCTIONS":       "economic sanctions OFAC restrictions",
    "SIG_ECO_SANCTIONS_ACTIVE": "active sanctions enforcement compliance",
    "SIG_ECO_PRESSURE_HIGH":   "economic pressure GDP decline inflation",
    "SIG_ECON_PRESSURE":       "economic pressure cost burden",
    "SIG_ECONOMIC_PRESSURE":   "economic pressure financial strain",
    "SIG_ECO_DEPENDENCY":      "economic dependency trade reliance",
    "SIG_TRADE_DISRUPTION":    "trade disruption supply chain break",
    "SIG_SANCTIONS_ACTIVE":    "sanctions enforcement active measures",
}

# Default reliability for MoltBot web sources (LOW — unverified)
_WEB_RELIABILITY = 0.35


# =====================================================================
# CollectionTask — the structured instruction MoltBot receives
# =====================================================================

@dataclass
class CollectionTask:
    """
    What MoltBot actually executes.

    This is NOT a search query.  It is a structured task:
        modality  — what kind of information
        country   — geographic scope
        topic     — domain keywords (from closed map)
        signal    — which analytical signal this serves
        limit     — max documents to retrieve
    """
    modality: str
    country: str
    topic: str
    signal: str
    limit: int = 5
    min_date: str = ""

    def to_moltbot_query(self) -> str:
        """
        Build the string MoltBot passes to its web search.

        Format:  "{country} {topic} {signal_hint}"
        This searches THE WORLD, not the user's question.
        """
        parts = []
        if self.country:
            parts.append(self.country)
        parts.append(self.topic)
        return " ".join(parts).strip()

    def to_moltbot_gaps(self) -> List[str]:
        """Structured missing_gaps for MoltBot payload."""
        return [self.signal]


# =====================================================================
# PIR → CollectionTask conversion
# =====================================================================

def pirs_to_tasks(
    pir_dicts: List[Dict[str, Any]],
    country: str = "",
    limit_per_pir: int = 5,
) -> List[CollectionTask]:
    """
    Convert PIR dicts (as passed through investigation_needs) into
    CollectionTasks that MoltBot can execute.

    Each PIR maps to exactly one task via the modality→topic table.
    PIRs whose modality has no topic mapping are skipped (e.g. HUMINT
    cannot be collected from the web).
    """
    tasks: List[CollectionTask] = []
    seen: set = set()

    for pir in pir_dicts:
        signal = str(pir.get("signal", "")).strip().upper()
        modality = str(pir.get("collection", "")).strip().upper()
        pir_country = str(pir.get("country", "")).strip() or country
        min_date = str(pir.get("min_date", "")).strip()

        if not signal or not modality:
            continue

        # Deduplicate by (signal, modality) — no redundant collection
        key = (signal, modality)
        if key in seen:
            continue
        seen.add(key)

        # Build topic from modality map + signal hint
        modality_topic = MODALITY_TOPIC_MAP.get(modality, "")
        if not modality_topic:
            logger.info(
                "[COLLECTION] Skipping PIR %s/%s — no web-collectible topic for modality",
                signal, modality,
            )
            continue

        signal_hint = SIGNAL_TOPIC_HINT.get(signal, "")
        topic = f"{modality_topic} {signal_hint}".strip()

        tasks.append(CollectionTask(
            modality=modality,
            country=pir_country,
            topic=topic,
            signal=signal,
            limit=limit_per_pir,
            min_date=min_date,
        ))

    return tasks


# =====================================================================
# MoltBot doc → signal_hit conversion
# =====================================================================

def _normalize_iso_date(value: Any) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    if len(token) >= 10 and token[4:5] == "-" and token[7:8] == "-":
        return token[:10]
    try:
        return datetime.fromisoformat(token.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _authoritative_doc_date(doc: Dict[str, Any]) -> tuple[str, str]:
    raw_obs = doc.get("raw_observation")
    if isinstance(raw_obs, dict):
        date_source = str(raw_obs.get("date_source", "") or "").strip().lower()
        source_type = str(raw_obs.get("source_type", raw_obs.get("source", "")) or "").strip().upper()
        obs_date = _normalize_iso_date(raw_obs.get("timestamp", ""))
        if obs_date and date_source not in {"crawl_time", "unknown", "crawl"}:
            return obs_date, date_source or "observation"
        if obs_date and source_type in {"DATASET", "SENSOR", "GOV", "UN", "SIPRI"}:
            return obs_date, date_source or source_type.lower()
        return "", date_source or "unknown"

    date = _normalize_iso_date(doc.get("date") or doc.get("published") or "")
    if date:
        return date, "document"
    return "", "unknown"


def _filter_docs_by_min_date(
    docs: List[Dict[str, Any]],
    *,
    min_date: str = "",
    label: str = "",
) -> List[Dict[str, Any]]:
    cutoff = _normalize_iso_date(min_date)
    if not cutoff:
        return docs

    kept: List[Dict[str, Any]] = []
    rejected_old = 0
    rejected_undated = 0

    for doc in docs:
        doc_date, _ = _authoritative_doc_date(doc)
        if not doc_date:
            rejected_undated += 1
            continue
        if doc_date < cutoff:
            rejected_old += 1
            continue
        kept.append(doc)

    if rejected_old or rejected_undated:
        logger.info(
            "[COLLECTION] Freshness filter %s cutoff=%s kept=%d rejected_old=%d rejected_undated=%d",
            label or "(unnamed)",
            cutoff,
            len(kept),
            rejected_old,
            rejected_undated,
        )
    return kept


def _doc_to_signal_hit(doc: Dict[str, Any], signal: str) -> Dict[str, Any]:
    """
    Convert a single MoltBot normalized document into a signal_hit dict.

    signal_hit format (consumed by state_provider.py evidence integrator):
        signal            — the PIR signal token (e.g. SIG_MIL_ESCALATION)
        score             — reliability score (LOW for web sources)
        source            — source name
        url               — document URL
        publication_date  — ISO date string
        excerpt           — first N chars of content
        source_id         — stable dedup key
    """
    content = str(doc.get("content") or doc.get("text") or "").strip()
    url = str(doc.get("url") or doc.get("source_url") or "").strip()
    title = str(doc.get("title") or "").strip()
    date, date_source = _authoritative_doc_date(doc)
    doc_id = str(doc.get("id") or "").strip()
    raw_observation = doc.get("raw_observation") if isinstance(doc.get("raw_observation"), dict) else None

    metadata = doc.get("metadata") or {}
    source_name = str(
        metadata.get("source")
        or metadata.get("search_engine")
        or "moltbot_web"
    )

    # Excerpt: title + first ~500 chars of content
    excerpt_parts = []
    if title:
        excerpt_parts.append(title)
    if content:
        excerpt_parts.append(content[:500])
    excerpt = " — ".join(excerpt_parts)[:600]

    source_id = doc_id or f"moltbot_{signal}_{date}_{hash(url) % 100000}"

    return {
        "signal": signal,
        "score": _WEB_RELIABILITY,
        "source": source_name,
        "url": url,
        "publication_date": date,
        "excerpt": excerpt,
        "source_id": source_id,
        "date_source": date_source,
        "raw_observation": raw_observation,
    }


# =====================================================================
# Main entry point — execute the full collection plan
# =====================================================================

def execute_collection_plan(
    pir_dicts: List[Dict[str, Any]],
    country: str = "",
    limit_per_pir: int = 5,
    max_total_docs: int = 25,
) -> List[Dict[str, Any]]:
    """
    Execute a PIR-driven collection plan via MoltBot.

    Steps:
        1. Convert PIR dicts → CollectionTasks (closed modality→topic map)
        2. For each task, call MoltBot.collect_documents()
        3. Convert raw docs → signal_hits
        4. Return signal_hits for evidence integration

    Returns:
        List of signal_hit dicts in the format expected by
        investigate_and_update()'s evidence integrator.

    If MoltBot is unavailable or all tasks fail, returns [].
    The investigation loop will still proceed with a state rebuild
    from existing data — this is a best-effort enrichment.
    """
    if not pir_dicts:
        return []

    # 1. PIR → tasks
    tasks = pirs_to_tasks(pir_dicts, country=country, limit_per_pir=limit_per_pir)
    if not tasks:
        logger.info("[COLLECTION] No web-collectible tasks from %d PIRs", len(pir_dicts))
        return []

    # 2. Import MoltBot (lazy — fails gracefully if not available)
    try:
        from engine.Layer1_Collection.api.moltbot_agent import moltbot_agent
    except ImportError as e:
        logger.warning("[COLLECTION] MoltBot import failed: %s — skipping web collection", e)
        return []

    # 3. Execute tasks
    all_signal_hits: List[Dict[str, Any]] = []
    total_docs = 0

    for task in tasks:
        if total_docs >= max_total_docs:
            logger.info("[COLLECTION] Document budget exhausted (%d/%d)", total_docs, max_total_docs)
            break

        remaining = max_total_docs - total_docs
        task_limit = min(task.limit, remaining)

        query = task.to_moltbot_query()
        logger.info(
            "[COLLECTION] MoltBot task: %s [%s] country=%s query='%s' (limit=%d)",
            task.signal, task.modality, task.country, query[:80], task_limit,
        )

        try:
            docs = moltbot_agent.collect_documents(
                query=query,
                required_evidence=[task.signal],
                countries=[task.country] if task.country else [],
                missing_gaps=task.to_moltbot_gaps(),
                limit=task_limit,
            )
        except Exception as e:
            logger.warning(
                "[COLLECTION] MoltBot failed for %s/%s: %s",
                task.signal, task.modality, e,
            )
            continue

        docs = _filter_docs_by_min_date(
            list(docs or []),
            min_date=task.min_date,
            label=f"{task.signal}/{task.modality}",
        )

        if not docs:
            logger.info(
                "[COLLECTION] MoltBot returned 0 docs for %s/%s",
                task.signal, task.modality,
            )
            continue

        # 4. Convert raw docs → signal_hits (PIR-tagged)
        for doc in docs:
            hit = _doc_to_signal_hit(doc, task.signal)
            all_signal_hits.append(hit)
            total_docs += 1

        # 5. Evidence Assimilation — read article content for ALL signals
        #    The PIR-tagged hit only covers the signal we searched for.
        #    The assimilator scans the text and may discover ADDITIONAL
        #    signals the PIR didn't ask about (e.g. searching for
        #    SIG_MIL_ESCALATION but the article also mentions protests).
        try:
            from engine.Layer2_Knowledge.assimilation.evidence_assimilator import extract_signals

            for doc in docs:
                content = str(doc.get("content") or doc.get("text") or "")
                if len(content) < 20:
                    continue
                url = str(doc.get("url") or doc.get("source_url") or "")
                date = str(doc.get("date") or "")
                assimilated = extract_signals(
                    content,
                    source="MOLTBOT",
                    article_date=date or None,
                    url=url,
                )
                for sig in assimilated:
                    # Skip if it duplicates the PIR-tagged signal we already emitted
                    if sig["signal"] == task.signal:
                        continue
                    all_signal_hits.append({
                        "signal": sig["signal"],
                        "score": sig["confidence"] * sig["reliability"],
                        "source": sig.get("source", "MOLTBOT"),
                        "url": sig.get("url", url),
                        "publication_date": _normalize_iso_date(sig.get("timestamp") or date),
                        "excerpt": content[:300],
                        "source_id": f"assimilated_{sig['signal']}_{hash(url) % 100000}",
                        "date_source": str((sig.get("_observation") or {}).get("date_source", "")),
                        "raw_observation": sig.get("_observation"),
                    })
                if assimilated:
                    logger.info(
                        "[COLLECTION] Assimilator found %d extra signal(s) in %s doc",
                        len([s for s in assimilated if s["signal"] != task.signal]),
                        task.signal,
                    )
        except ImportError:
            pass  # assimilator not available — degrade gracefully

        logger.info(
            "[COLLECTION] MoltBot collected %d docs for %s [%s] -> %d total hits",
            len(docs), task.signal, task.modality, len(all_signal_hits),
        )

    logger.info(
        "[COLLECTION] Collection plan complete: %d signal_hits from %d tasks",
        len(all_signal_hits), len(tasks),
    )
    return all_signal_hits


# =====================================================================
# Directed Collection — Hypothesis Expansion + Observation Extraction
# =====================================================================

def execute_directed_collection(
    pir_dicts: List[Dict[str, Any]],
    state_context: Any = None,
    country: str = "",
    max_observables_per_signal: int = 5,
    max_total_docs: int = 20,
) -> Dict[str, Any]:
    """
    Execute hypothesis-driven directed collection.

    This is the UPGRADED collection path that replaces generic searching
    with directed intelligence collection:

        1. Missing signal → Hypothesis Expansion (what traces to look for)
        2. Observable indicators → Directed search (specific queries)
        3. Raw documents → Observation extraction (what did we see?)
        4. Observations → Belief Accumulator (do we believe it?)
        5. Beliefs → State update (coverage increases)

    Parameters
    ----------
    pir_dicts : list[dict]
        PIR dicts with at minimum {"signal": "SIG_..."}.
    state_context : StateContext, optional
        If provided, beliefs are applied directly to this state.
    country : str
        Country name or ISO code.
    max_observables_per_signal : int
        Max observable queries per signal.
    max_total_docs : int
        Global document cap.

    Returns
    -------
    dict with keys:
        observations : list[dict]   — extracted observation records
        beliefs : list[dict]        — promoted beliefs
        signals_updated : list[str] — signals whose confidence changed
        documents_collected : int   — raw documents retrieved
        signals_searched : list[str] — which signals were expanded
    """
    from engine.Layer4_Analysis.hypothesis.hypothesis_expander import expand_signal
    from Core.intelligence.moltbot_adapter import directed_search_batch

    result = {
        "observations": [],
        "beliefs": [],
        "signals_updated": [],
        "documents_collected": 0,
        "signals_searched": [],
    }

    if not pir_dicts:
        return result

    # Resolve country name for search context, keep ISO code for GDELT
    country_name = _resolve_country_name(country)
    country_iso = country.strip().upper() if len(country.strip()) == 3 else ""

    # 1. Signal → Observable Expansion (with parallel signal code tracking)
    all_observables: List[str] = []
    signal_min_dates: Dict[str, str] = {}
    all_signal_codes: List[str] = []   # parallel list: signal_codes[i] → observables[i]
    for pir in pir_dicts:
        signal = str(pir.get("signal", "")).strip().upper()
        if not signal:
            continue
        signal_min_dates[signal] = str(pir.get("min_date", "") or "").strip()

        result["signals_searched"].append(signal)
        observables = expand_signal(signal)

        if not observables:
            # No expansion defined — use signal topic hint as fallback
            hint = SIGNAL_TOPIC_HINT.get(signal, signal.replace("SIG_", "").replace("_", " ").lower())
            observables = [hint]

        # Cap per signal
        observables = observables[:max_observables_per_signal]

        logger.info(
            "[DIRECTED-COLLECTION] %s → %d observables: %s",
            signal, len(observables),
            ", ".join(o[:30] for o in observables[:3]) + ("..." if len(observables) > 3 else ""),
        )
        all_observables.extend(observables)
        all_signal_codes.extend([signal] * len(observables))

    if not all_observables:
        logger.info("[DIRECTED-COLLECTION] No observables to search")
        return result

    # 2. Directed search for all observables (pass signal codes for GDELT matching)
    documents = directed_search_batch(
        observables=all_observables,
        country=country_name,
        max_results_per=3,
        max_total=max_total_docs,
        signal_codes=all_signal_codes,
        country_iso=country_iso,
    )
    filtered_documents: List[Dict[str, Any]] = []
    for doc in list(documents or []):
        signal_hint = str(
            doc.get("signal_hint")
            or (doc.get("raw_observation") or {}).get("signal")
            or ""
        ).strip().upper()
        min_date = signal_min_dates.get(signal_hint, "")
        if not min_date:
            filtered_documents.append(doc)
            continue
        filtered_documents.extend(
            _filter_docs_by_min_date(
                [doc],
                min_date=min_date,
                label=f"directed:{signal_hint}",
            )
        )
    documents = filtered_documents
    result["documents_collected"] = len(documents)

    if not documents:
        logger.info("[DIRECTED-COLLECTION] No documents found for %d observables", len(all_observables))
        return result

    logger.info(
        "[DIRECTED-COLLECTION] Collected %d documents from %d observable queries",
        len(documents), len(all_observables),
    )

    # 3. Extract observations from documents
    #    GDELT_DIRECTED docs may already carry raw_observation — use those
    #    directly instead of re-extracting via keyword matching.
    try:
        from engine.Layer2_Knowledge.assimilation.evidence_assimilator import extract_observations

        all_obs: List[Dict[str, Any]] = []
        seen_origins: set = set()

        for doc in documents:
            # ── Fast path: GDELT docs carry raw observations already ──
            raw_obs = doc.get("raw_observation")
            if raw_obs and isinstance(raw_obs, dict) and raw_obs.get("signal"):
                origin_id = str(raw_obs.get("origin_id", ""))
                if origin_id and origin_id in seen_origins:
                    continue
                seen_origins.add(origin_id)
                all_obs.append(raw_obs)
                continue

            # ── Slow path: non-GDELT docs need keyword extraction ────
            text = str(doc.get("text", ""))
            if len(text) < 15:
                continue

            src_type = str(doc.get("source", "OSINT")).upper()
            url = str(doc.get("url", ""))
            date = str(doc.get("date", ""))

            obs_list = extract_observations(
                article_text=text,
                source_type=src_type,
                article_date=date or None,
                url=url,
            )

            for obs in obs_list:
                origin_id = obs.get("origin_id", "")
                if origin_id and origin_id in seen_origins:
                    continue  # Deduplicate across documents
                seen_origins.add(origin_id)
                all_obs.append(obs)

        result["observations"] = all_obs
        logger.info(
            "[DIRECTED-COLLECTION] Extracted %d observations from %d documents",
            len(all_obs), len(documents),
        )
    except ImportError as e:
        logger.warning("[DIRECTED-COLLECTION] Observation extractor unavailable: %s", e)
        return result

    if not result["observations"]:
        return result

    # 4. Belief Accumulation
    try:
        from engine.Layer3_StateModel.belief_accumulator import BeliefAccumulator, apply_beliefs_to_state

        acc = BeliefAccumulator()
        beliefs = acc.evaluate(result["observations"])
        result["beliefs"] = beliefs

        # 5. Apply beliefs to state if provided
        if state_context is not None and beliefs:
            updated = apply_beliefs_to_state(state_context, beliefs)
            result["signals_updated"] = updated
            logger.info(
                "[DIRECTED-COLLECTION] %d beliefs promoted, %d signals updated in state",
                len(beliefs), len(updated),
            )
        elif beliefs:
            logger.info(
                "[DIRECTED-COLLECTION] %d beliefs promoted (no state to update)",
                len(beliefs),
            )

    except ImportError as e:
        logger.warning("[DIRECTED-COLLECTION] Belief accumulator unavailable: %s", e)

    return result


def _resolve_country_name(country_code: str) -> str:
    """Convert a country reference to a search-friendly canonical name."""
    return resolve_country_name(country_code)


__all__ = [
    "CollectionTask",
    "MODALITY_TOPIC_MAP",
    "SIGNAL_TOPIC_HINT",
    "pirs_to_tasks",
    "execute_collection_plan",
    "execute_directed_collection",
]
