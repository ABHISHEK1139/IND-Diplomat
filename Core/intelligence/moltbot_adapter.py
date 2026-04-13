"""
MoltBot Directed Intelligence Adapter
=======================================

Bridges the DIP perception layer and investigation layer to the
MoltBot web sensor.

TWO MODES OF OPERATION:

1. **Perception mode** (run_batch_collection) — called from state_builder
   BEFORE the council convenes.  Searches by COUNTRY TOPICS (activity
   spaces), NOT by signal codes.  Acts like a sensor sweep — same
   category as GDELT.  This is the primary mode.

2. **Investigation mode** (directed_search_batch) — called from the
   Gate→Collection loop AFTER the council has already reasoned.
   Searches by signal-specific queries when the gate withholds.  This
   is a secondary top-up for gaps.

Architecture:
    GDELT   = radar   (structured CAMEO events)
    MoltBot = camera  (narrative article text → pattern-extracted observations)
    Both → Belief Accumulator → State Model → Council → Gate
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Set

from Utils.country_normalization import resolve_country_iso, resolve_country_name

logger = logging.getLogger("Core.intelligence.moltbot_adapter")

# ── Per-country sweep cooldown (prevents DDoS during loops) ─────────
_LAST_SWEEP: Dict[str, float] = {}
_SWEEP_COOLDOWN = 900.0  # seconds — MoltBot re-sweeps at most every 15 min
_SWEEP_CACHE: Dict[str, List[Dict[str, Any]]] = {}  # country_iso → observations

# =====================================================================
# Signal kinship map — when looking for SIG_FORCE_POSTURE, observations
# tagged SIG_MIL_ESCALATION are also partially relevant, etc.
# =====================================================================
_SIGNAL_KIN: Dict[str, Set[str]] = {
    "SIG_FORCE_POSTURE":          {"SIG_MIL_ESCALATION"},
    "SIG_MIL_ESCALATION":         {"SIG_FORCE_POSTURE"},
    "SIG_CYBER_ACTIVITY":         {"SIG_COERCIVE_BARGAINING", "SIG_COERCIVE_PRESSURE"},
    "SIG_ECON_PRESSURE":          {"SIG_COERCIVE_BARGAINING", "SIG_ECO_SANCTIONS_ACTIVE"},
    "SIG_ECO_SANCTIONS_ACTIVE":   {"SIG_ECON_PRESSURE", "SIG_COERCIVE_BARGAINING"},
    "SIG_DIP_HOSTILITY":          {"SIG_NEGOTIATION_BREAKDOWN", "SIG_COERCIVE_BARGAINING"},
    "SIG_NEGOTIATION_BREAKDOWN":  {"SIG_DIP_HOSTILITY"},
    "SIG_INTERNAL_INSTABILITY":   {"SIG_COERCIVE_PRESSURE"},
    "SIG_COERCIVE_PRESSURE":      {"SIG_INTERNAL_INSTABILITY"},
    "SIG_COERCIVE_BARGAINING":    {"SIG_DIP_HOSTILITY", "SIG_COERCIVE_PRESSURE"},
    "SIG_DIPLOMACY_ACTIVE":       set(),
}

# ── Module-level GDELT cache to avoid redundant HTTP calls ──────────
_gdelt_cache: Dict[str, List[Dict[str, Any]]] = {}
_gdelt_cache_ts: float = 0.0
_GDELT_CACHE_TTL = 120.0  # seconds


# =====================================================================
# BATCH PERCEPTION: run_batch_collection (for state builder)
# =====================================================================

def run_batch_collection(country_iso: str, max_articles: int = 15) -> List[Dict[str, Any]]:
    """
    Run MoltBot as a PERCEPTION SENSOR — searches by country activity space.

    Called from state_provider.build_initial_state(), BEFORE the council.
    Returns observation dicts in the SAME format as GDELT sensor so
    the BeliefAccumulator can evaluate them identically.

    Architecture:
        1. Look up country topics (activity spaces, NOT signals)
        2. For each topic: web_search → fetch articles → extract observations
        3. Deduplicate by origin_id
        4. Return raw observations (same schema as GDELT)

    Cooldown: at most one sweep per country per 15 minutes.  Returns
    cached observations if called again within the window.

    Parameters
    ----------
    country_iso : str
        ISO 3-letter code (e.g. "IRN").
    max_articles : int
        Maximum articles to fetch across all topics.

    Returns
    -------
    list[dict]
        Observation dicts: {type, signal, source_type, evidence_strength,
        corroboration, keyword_hits, origin_id, source, url, timestamp, excerpt}
    """
    global _LAST_SWEEP, _SWEEP_CACHE

    iso = resolve_country_iso(country_iso)
    if not iso:
        logger.warning("[MOLTBOT-PERCEPTION] Could not resolve country '%s' to ISO", country_iso)
        return []
    now = time.time()

    # Cooldown — return cached observations if within window
    if iso in _LAST_SWEEP and (now - _LAST_SWEEP[iso]) < _SWEEP_COOLDOWN:
        cached = _SWEEP_CACHE.get(iso, [])
        if cached:
            logger.info(
                "[MOLTBOT-PERCEPTION] Returning %d cached observations for %s (%.0fs ago)",
                len(cached), iso, now - _LAST_SWEEP[iso],
            )
        return cached

    try:
        from Core.intelligence.moltbot_topics import get_topics
        from engine.Layer1_Collection.sensors.moltbot_sensor import (
            web_search, fetch_article,
        )
        from engine.Layer1_Collection.moltbot_observation_extractor import extract_observations
        from engine.Layer1_Collection.sensors.relevance_filter import (
            score_relevance, RELEVANCE_THRESHOLD,
        )
        from engine.Layer1_Collection.sensors.event_classifier import extract_headline
    except ImportError as e:
        logger.debug("[MOLTBOT-PERCEPTION] Import failed: %s", e)
        return []

    # Resolve country name for search prefix
    country_name = resolve_country_name(iso)
    topics = get_topics(iso)

    logger.info(
        "[MOLTBOT-PERCEPTION] Sensor sweep: %s (%s), %d topics, max %d articles",
        country_name, iso, len(topics), max_articles,
    )

    all_observations: List[Dict[str, Any]] = []
    seen_urls: set = set()
    seen_origins: set = set()
    total_fetched = 0

    for topic in topics:
        if total_fetched >= max_articles:
            break

        query = f"{country_name} {topic}"

        try:
            search_results = web_search(query, max_results=5)
        except Exception as e:
            logger.debug("[MOLTBOT-PERCEPTION] Search failed for '%s': %s", query, e)
            continue

        for sr in search_results:
            if total_fetched >= max_articles:
                break

            url = sr.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            try:
                result = fetch_article(url)
                # Handle both 2-tuple (legacy) and 3-tuple (new) returns
                if len(result) == 3:
                    text, pub_date, date_strategy = result
                else:
                    text, pub_date = result[0], result[1]
                    date_strategy = ""
            except Exception:
                continue
            if not text or len(text) < 80:
                continue

            # ── Extract headline for relevance & eventness ───────
            headline = extract_headline(text)

            # ── Relevance filter ─────────────────────────────────
            # Reject articles that don't actually discuss the target
            # country (e.g. India article for Iran query).
            relevance = score_relevance(text, iso, headline=headline)
            if relevance < RELEVANCE_THRESHOLD:
                logger.info(
                    "[RELEVANCE] Rejected: %s (score=%.2f, country=%s)",
                    url[:60], relevance, iso,
                )
                continue

            total_fetched += 1

            # Extract ALL signals from this article (not targeted)
            obs_list = extract_observations(text=text, url=url, source_type="OSINT",
                                            publish_date=pub_date,
                                            date_strategy=date_strategy,
                                            headline=headline)

            for obs in obs_list:
                origin = obs.get("origin_id", "")
                if origin and origin in seen_origins:
                    continue
                seen_origins.add(origin)
                all_observations.append(obs)

    _LAST_SWEEP[iso] = time.time()
    _SWEEP_CACHE[iso] = all_observations

    logger.info(
        "[MOLTBOT-PERCEPTION] Sweep complete: %d articles → %d observations for %s",
        total_fetched, len(all_observations), iso,
    )

    return all_observations


def directed_search(
    observable: str,
    country: str = "",
    max_results: int = 5,
    signal_code: str = "",
    country_iso: str = "",
) -> List[Dict[str, Any]]:
    """
    Execute a directed search for a specific real-world observable.

    Parameters
    ----------
    observable : str
        A concrete search term (e.g. "troop deployment", "missile test").
    country : str
        Country name to scope the search query.
    max_results : int
        Maximum documents to return.
    signal_code : str
        The parent signal (e.g. "SIG_FORCE_POSTURE") — used for
        signal-code matching against GDELT observations.
    country_iso : str
        ISO 3-letter country code (e.g. "IRN") for GDELT queries.

    Returns
    -------
    list[dict]
        Each dict has: text, url, source, date, signal_hint, raw_observation.
    """
    query = f"{country} {observable}".strip() if country else observable

    # Attempt 1: MoltBot (primary collection agent)
    docs = _try_moltbot(query, max_results)
    if docs:
        return docs

    # Attempt 2: GDELT live sensor (signal-code matching + keyword fallback)
    docs = _try_gdelt_directed(observable, country_iso or country, max_results, signal_code)
    if docs:
        return docs

    logger.info("[DIRECTED] No results for: %s", query)
    return []


def directed_search_batch(
    observables: List[str],
    country: str = "",
    max_results_per: int = 3,
    max_total: int = 20,
    signal_codes: Optional[List[str]] = None,
    country_iso: str = "",
) -> List[Dict[str, Any]]:
    """
    Search for multiple observables using BOTH sensors in parallel.

    Collection strategy (two sensors):
        1. MoltBot web sensor (batch) — searches open web for all unique
           signals at once, fetches articles, extracts observations.
        2. GDELT signal matching (per-observable) — matches cached GDELT
           events by signal code + kinship + keyword.

    Both produce documents in the same format.  Deduplicated by origin_id.

    Parameters
    ----------
    observables : list[str]
        Observable indicator phrases.
    country : str
        Country name for search queries.
    max_results_per : int
        Max results per observable.
    max_total : int
        Global result cap.
    signal_codes : list[str], optional
        Parallel list of signal codes (same length as observables).
    country_iso : str
        ISO 3-letter country code (e.g. "IRN") for GDELT queries.

    Returns
    -------
    list[dict]
        Combined document results from both sensors.
    """
    all_docs: List[Dict[str, Any]] = []
    seen_origins: set = set()

    def _add_doc(doc: Dict[str, Any]) -> bool:
        """Add doc if not duplicate. Returns True if added."""
        if len(all_docs) >= max_total:
            return False
        origin = doc.get("origin_id", doc.get("url", ""))
        if origin and origin in seen_origins:
            return False
        seen_origins.add(origin)
        all_docs.append(doc)
        return True

    # ── Phase 1: MoltBot web sensor (batch, best-effort) ──────────
    unique_signals = list(dict.fromkeys(
        sig for sig in (signal_codes or []) if sig
    ))
    moltbot_docs = _try_moltbot_batch(unique_signals, country, country_iso)
    for doc in moltbot_docs:
        _add_doc(doc)

    moltbot_count = len(all_docs)
    if moltbot_count:
        logger.info(
            "[DIRECTED] MoltBot sensor: %d documents for %d signals",
            moltbot_count, len(unique_signals),
        )

    # ── Phase 2: GDELT signal matching (per-observable) ───────────
    _warm_gdelt_cache(country_iso or country)

    for i, obs in enumerate(observables):
        if len(all_docs) >= max_total:
            break

        remaining = max_total - len(all_docs)
        limit = min(max_results_per, remaining)
        sig = (signal_codes[i] if signal_codes and i < len(signal_codes) else "")

        docs = _try_gdelt_directed(obs, country_iso or country, limit, sig)
        for doc in docs:
            _add_doc(doc)

    gdelt_count = len(all_docs) - moltbot_count

    logger.info(
        "[DIRECTED] Batch search: %d observables → %d documents "
        "(MoltBot=%d, GDELT=%d)",
        len(observables), len(all_docs), moltbot_count, gdelt_count,
    )
    return all_docs


def _resolve_to_iso(country: str) -> str:
    """Resolve a country reference to an ISO 3-letter code for GDELT."""
    return resolve_country_iso(country)


def _warm_gdelt_cache(country: str) -> None:
    """Pre-fetch GDELT observations into module-level cache."""
    import time
    global _gdelt_cache, _gdelt_cache_ts

    now = time.time()
    iso = _resolve_to_iso(country) if country else ""
    if not iso:
        if country:
            logger.warning("[DIRECTED] Skipping GDELT warmup: unresolved country '%s'", country)
        return

    # Already warm and fresh?
    if iso in _gdelt_cache and (now - _gdelt_cache_ts) < _GDELT_CACHE_TTL:
        return

    try:
        from engine.Layer1_Collection.sensors.gdelt_sensor import sense_gdelt
        obs = sense_gdelt(countries=[iso])
        _gdelt_cache[iso] = obs
        _gdelt_cache_ts = now
        logger.info("[DIRECTED] GDELT cache warmed: %d observations for %s", len(obs), iso)
    except ImportError:
        logger.debug("[DIRECTED] GDELT sensor not available for caching")
    except Exception as e:
        logger.debug("[DIRECTED] GDELT cache warm failed: %s", e)


# =====================================================================
# MoltBot web sensor — batch collection
# =====================================================================

def _try_moltbot(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Try MoltBot for a single directed web search query."""
    try:
        from engine.Layer1_Collection.sensors.moltbot_sensor import (
            web_search, fetch_article,
        )
        from engine.Layer1_Collection.moltbot_observation_extractor import extract_observations

        # Search the web
        search_results = web_search(query, max_results=max_results + 2)
        if not search_results:
            return []

        docs: List[Dict[str, Any]] = []
        for sr in search_results[:max_results]:
            url = sr.get("url", "")
            if not url:
                continue

            # Fetch article text
            result = fetch_article(url)
            if len(result) == 3:
                article_text, pub_date, date_strategy = result
            else:
                article_text, pub_date = result[0], result[1]
                date_strategy = ""
            if not article_text or len(article_text) < 50:
                continue

            # Extract observations from article
            obs_list = extract_observations(text=article_text, url=url,
                                            publish_date=pub_date,
                                            date_strategy=date_strategy)

            # Build doc for each observation found
            for obs in obs_list:
                docs.append({
                    "text": obs.get("excerpt", ""),
                    "url": url,
                    "source": "MOLTBOT",
                    "date": obs.get("timestamp", ""),
                    "signal_hint": obs.get("signal", ""),
                    "origin_id": obs.get("origin_id", ""),
                    "matched_by": "moltbot_article",
                    "raw_observation": obs,
                })

            # If no pattern matched, still return article as raw doc
            if not obs_list and article_text:
                docs.append({
                    "text": article_text[:500],
                    "url": url,
                    "source": "MOLTBOT",
                    "date": "",
                    "signal_hint": "",
                    "origin_id": "",
                    "matched_by": "moltbot_raw",
                })

        if docs:
            logger.info("[DIRECTED] MoltBot returned %d docs for: %s", len(docs), query[:60])
        return docs

    except ImportError:
        return []  # MoltBot sensor not installed — fall through to GDELT
    except Exception as e:
        logger.debug("[DIRECTED] MoltBot error: %s", e)
        return []


def _try_moltbot_batch(
    signals: List[str],
    country: str = "",
    country_iso: str = "",
) -> List[Dict[str, Any]]:
    """
    Run MoltBot web sensor for a batch of signals.

    This is the primary collection path for narrative evidence.
    It runs ONCE for all unique signals (not per-observable).

    Pipeline (no LLM):
        1. Signals → search queries (mapping table)
        2. Search queries → URLs (DuckDuckGo / Bing RSS)
        3. URLs → article text (requests + BeautifulSoup)
        4. Article text → observations (regex pattern matching)
        5. Observations wrapped as document dicts
    """
    if not signals:
        return []

    try:
        from engine.Layer1_Collection.sensors.moltbot_sensor import sense_moltbot

        # Resolve country name for search context
        country_name = country
        if country_iso and not country:
            country_name = resolve_country_name(country_iso)

        # Run the sensor sweep
        observations = sense_moltbot(
            signals=signals,
            country=country_name,
            max_queries_per_signal=2,
            max_articles_per_signal=3,
            max_total_articles=15,
        )

        if not observations:
            logger.info("[DIRECTED] MoltBot sensor: 0 observations for %d signals", len(signals))
            return []

        # Wrap observations as document dicts (same format as GDELT docs)
        docs: List[Dict[str, Any]] = []
        for obs in observations:
            docs.append({
                "text": obs.get("excerpt", ""),
                "url": obs.get("url", ""),
                "source": "MOLTBOT",
                "date": obs.get("timestamp", ""),
                "signal_hint": obs.get("signal", ""),
                "origin_id": obs.get("origin_id", ""),
                "matched_by": "moltbot_article",
                "raw_observation": obs,
            })

        logger.info(
            "[DIRECTED] MoltBot sensor: %d observations → %d docs from %d signals",
            len(observations), len(docs), len(signals),
        )
        return docs

    except ImportError as e:
        logger.debug("[DIRECTED] MoltBot sensor unavailable: %s", e)
        return []
    except Exception as e:
        logger.warning("[DIRECTED] MoltBot sensor error: %s", e)
        return []


# =====================================================================
# GDELT directed fallback — signal-code + keyword matching
# =====================================================================

def _try_gdelt_directed(
    observable: str,
    country: str,
    max_results: int,
    signal_code: str = "",
) -> List[Dict[str, Any]]:
    """
    Match cached GDELT observations against the target signal.

    Matching strategy (in order of priority):
    1. EXACT signal match — obs["signal"] == signal_code
    2. KIN signal match  — obs["signal"] in related signals for signal_code
    3. Keyword match      — observable keywords appear in obs excerpt
    """
    iso = _resolve_to_iso(country) if country else ""
    if country and not iso:
        logger.warning("[DIRECTED] Skipping GDELT match: unresolved country '%s'", country)
        return []

    # Use cached observations (pre-warmed by directed_search_batch)
    observations = _gdelt_cache.get(iso, [])
    if not observations:
        # Cold start — try to fetch
        _warm_gdelt_cache(country)
        observations = _gdelt_cache.get(iso, [])
    if not observations:
        return []

    matched: List[Dict[str, Any]] = []
    signal_upper = signal_code.strip().upper()

    # Build kin set for this signal
    kin_signals = _SIGNAL_KIN.get(signal_upper, set())
    match_signals = {signal_upper} | kin_signals if signal_upper else set()

    # Keyword fallback tokens (words with 4+ chars)
    observable_lower = observable.lower()
    keywords = [kw for kw in observable_lower.split() if len(kw) >= 4]

    for obs in observations:
        obs_signal = str(obs.get("signal", "")).strip().upper()
        obs_text = _obs_to_text(obs).lower()
        matched_by = ""

        # Priority 1: exact signal match
        if signal_upper and obs_signal == signal_upper:
            matched_by = "signal_exact"
        # Priority 2: kin signal match
        elif match_signals and obs_signal in kin_signals:
            matched_by = "signal_kin"
        # Priority 3: keyword match in excerpt
        elif keywords and any(kw in obs_text for kw in keywords):
            matched_by = "keyword"
        else:
            continue

        origin_id = str(obs.get("origin_id", ""))
        matched.append({
            "text": _obs_to_text(obs),
            "url": str(obs.get("url") or obs.get("source_url") or ""),
            "source": "GDELT_DIRECTED",
            "date": str(obs.get("timestamp") or obs.get("date") or ""),
            "signal_hint": obs_signal,
            "origin_id": origin_id,
            "matched_by": matched_by,
            "raw_observation": obs,
        })

        if len(matched) >= max_results:
            break

    if matched:
        logger.info(
            "[DIRECTED] GDELT matched %d/%d obs for %s ('%s'): %s",
            len(matched), len(observations),
            signal_upper or "?", observable[:30],
            ", ".join(d["matched_by"] for d in matched[:5]),
        )

    return matched


def _obs_to_text(obs: Any) -> str:
    """Convert a GDELT observation (dict or object) to searchable text.

    GDELT observations have: signal, excerpt, source_type, evidence_strength,
    corroboration, source, url, timestamp.  NOT action_type or description.
    """
    if isinstance(obs, dict):
        parts = [
            str(obs.get("signal", "")),
            str(obs.get("excerpt", "")),
            str(obs.get("source", "")),
        ]
        return " ".join(p for p in parts if p and p != "None")

    # Dataclass / namedtuple
    parts = []
    for attr in ("signal", "excerpt", "description", "source"):
        val = getattr(obs, attr, None)
        if val:
            parts.append(str(val))
    return " ".join(parts)
