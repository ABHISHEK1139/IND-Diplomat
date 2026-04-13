"""
Evidence Assimilator — converts raw text (articles, OSINT, scraped pages)
into **observations**, not beliefs.

Architecture (3-layer epistemic model):
    Evidence   — raw text from the world (article body, scraped page)
    Observation — "I think I saw something" (this module's output)
    Belief     — "I'm confident this is happening" (state model's job)

An observation is a *candidate perception*.  It does NOT update the
world model directly.  It must pass through the Belief Accumulator
(state_builder.ingest_observations) which requires **corroboration**
before promoting an observation to a belief.

Why this matters:
    A random blog post saying "troops mobilize" should NOT
    immediately alter a geopolitical assessment.  That's how
    intelligence failures happen (Iraq WMD problem).
    Observations must accumulate evidence from independent sources
    before the state model treats them as real.

Usage
-----
    from engine.Layer2_Knowledge.assimilation.evidence_assimilator import extract_observations

    observations = extract_observations(article_text, source_type="OSINT")
    # observations are candidates — NOT beliefs yet
    state_model.update_beliefs_from_observations(observations)

Each returned observation dict:
    {
        "type":              "observation",
        "signal":            "SIG_MIL_MOBILIZATION",
        "source_type":       "OSINT",
        "evidence_strength": 0.39,        # how strong THIS observation is
        "corroboration":     1,           # number of independent indicators
        "keyword_hits":      2,           # how many keywords matched
        "source":            "NEWS",
        "url":               "https://...",
        "timestamp":         "2026-03-01T06:18:00",
        "excerpt":           "...first 200 chars...",
    }
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Layer2.assimilation.evidence_assimilator")

# ── keyword → signal mapping ────────────────────────────────────────
# Each key is a plain-text phrase (lowercased at match time).
# Values are the canonical signal codes used throughout the pipeline.
KEYWORD_SIGNALS: Dict[str, str] = {
    # Military capability / mobilization
    "troop":              "SIG_MIL_MOBILIZATION",
    "troops":             "SIG_MIL_MOBILIZATION",
    "deployment":         "SIG_MIL_MOBILIZATION",
    "mobilization":       "SIG_MIL_MOBILIZATION",
    "mobilisation":       "SIG_MIL_MOBILIZATION",
    "reserve call-up":    "SIG_MIL_MOBILIZATION",
    "reservists":         "SIG_MIL_MOBILIZATION",
    # Force posture
    "airbase":            "SIG_FORCE_POSTURE",
    "air base":           "SIG_FORCE_POSTURE",
    "fighter jet":        "SIG_FORCE_POSTURE",
    "aircraft carrier":   "SIG_FORCE_POSTURE",
    "naval exercise":     "SIG_FORCE_POSTURE",
    "military exercise":  "SIG_FORCE_POSTURE",
    "war game":           "SIG_FORCE_POSTURE",
    "wargame":            "SIG_FORCE_POSTURE",
    # Escalation
    "missile":            "SIG_MIL_ESCALATION",
    "rocket":             "SIG_MIL_ESCALATION",
    "airstrike":          "SIG_MIL_ESCALATION",
    "air strike":         "SIG_MIL_ESCALATION",
    "bombing":            "SIG_MIL_ESCALATION",
    "shelling":           "SIG_MIL_ESCALATION",
    "artillery":          "SIG_MIL_ESCALATION",
    "drone strike":       "SIG_MIL_ESCALATION",
    # Logistics
    "supply line":        "SIG_LOGISTICS_PREP",
    "ammunition shipment": "SIG_LOGISTICS_PREP",
    "arms transfer":      "SIG_LOGISTICS_PREP",
    "weapons shipment":   "SIG_LOGISTICS_PREP",
    # Cyber
    "cyber attack":       "SIG_CYBER_ACTIVITY",
    "cyberattack":        "SIG_CYBER_ACTIVITY",
    "hack":               "SIG_CYBER_ACTIVITY",
    "ransomware":         "SIG_CYBER_ACTIVITY",
    "ddos":               "SIG_CYBER_ACTIVITY",
    # Economic pressure
    "sanction":           "SIG_ECONOMIC_PRESSURE",
    "sanctions":          "SIG_ECONOMIC_PRESSURE",
    "trade embargo":      "SIG_ECONOMIC_PRESSURE",
    "embargo":            "SIG_ECONOMIC_PRESSURE",
    "tariff":             "SIG_ECONOMIC_PRESSURE",
    "asset freeze":       "SIG_ECONOMIC_PRESSURE",
    # Internal instability
    "protest":            "SIG_INTERNAL_INSTABILITY",
    "riot":               "SIG_INTERNAL_INSTABILITY",
    "civil unrest":       "SIG_INTERNAL_INSTABILITY",
    "martial law":        "SIG_INTERNAL_INSTABILITY",
    "curfew":             "SIG_INTERNAL_INSTABILITY",
    "crackdown":          "SIG_INTERNAL_INSTABILITY",
    # Diplomatic hostility
    "embassy closed":     "SIG_DIP_HOSTILITY",
    "embassy closure":    "SIG_DIP_HOSTILITY",
    "diplomat expelled":  "SIG_DIP_HOSTILITY",
    "diplomatic expulsion": "SIG_DIP_HOSTILITY",
    "recall ambassador":  "SIG_DIP_HOSTILITY",
    "ambassador recalled": "SIG_DIP_HOSTILITY",
    "severed relations":  "SIG_DIP_HOSTILITY",
    # Alliance shifts
    "mutual defense":     "SIG_ALLIANCE_ACTIVATION",
    "defense pact":       "SIG_ALLIANCE_ACTIVATION",
    "nato article 5":     "SIG_ALLIANCE_ACTIVATION",
    "alliance":           "SIG_ALLIANCE_SHIFT",
    "coalition":          "SIG_ALLIANCE_SHIFT",
    # Deception
    "disinformation":     "SIG_DECEPTION_ACTIVITY",
    "propaganda":         "SIG_DECEPTION_ACTIVITY",
    "false flag":         "SIG_DECEPTION_ACTIVITY",
    # Negotiation breakdown
    "talks collapsed":    "SIG_NEGOTIATION_BREAKDOWN",
    "negotiations failed": "SIG_NEGOTIATION_BREAKDOWN",
    "ceasefire violated": "SIG_NEGOTIATION_BREAKDOWN",
    "ceasefire broken":   "SIG_NEGOTIATION_BREAKDOWN",
    "walked out of talks": "SIG_NEGOTIATION_BREAKDOWN",
    # Cooperative / de-escalation (GDELT sensor generates these structurally)
    "peace talks":         "SIG_DIPLOMACY_ACTIVE",
    "diplomatic meeting":  "SIG_DIPLOMACY_ACTIVE",
    "summit":              "SIG_DIPLOMACY_ACTIVE",
    "ceasefire agreement": "SIG_DIPLOMACY_ACTIVE",
    "peace agreement":     "SIG_DIPLOMACY_ACTIVE",
}

# ── Source reliability tiers ────────────────────────────────────────
# These determine how much a single observation from this source
# contributes to evidence_strength.  OSINT is LOW — it takes
# multiple OSINT observations to form a belief.
# Datasets and sensors are HIGH — a single reading is credible.
SOURCE_RELIABILITY: Dict[str, float] = {
    "SOCIAL":      0.30,
    "OSINT":       0.40,
    "MOLTBOT":     0.40,
    "NEWS":        0.55,
    "GOV":         0.75,
    "UN":          0.80,
    "SIPRI":       0.85,
    "SENSOR":      0.90,
    "ANALYST":     0.90,
    "DATASET":     0.90,
}

# Base keyword-match confidence — "I detected a keyword, not verified"
_BASE_KEYWORD_CONFIDENCE = 0.50


def _compute_origin_id(signal: str, excerpt: str) -> str:
    """
    Compute a stable origin fingerprint for deduplication.

    If 5 websites copy the same statement ("Iran moved missiles near
    the border"), they should count as ONE observation, not five.

    The origin_id is a hash of the signal + a normalized excerpt.
    Normalization: lowercase, collapse whitespace, take first 120 chars.
    """
    normalized = " ".join(excerpt.lower().split())[:120]
    raw = f"{signal}:{normalized}"
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


# =====================================================================
# Public API
# =====================================================================

def extract_observations(
    article_text: str,
    source_type: str = "OSINT",
    article_date: Optional[str] = None,
    url: str = "",
) -> List[Dict[str, Any]]:
    """
    Scan *article_text* for keyword matches and return **observations**.

    An observation is "I think I saw something" — it is NOT a belief.
    It must pass through the Belief Accumulator for corroboration
    before it can update the state model.

    Parameters
    ----------
    article_text : str
        Raw text content (article body, scraped page, etc.).
    source_type : str
        Source category: ``"OSINT"``, ``"NEWS"``, ``"GOV"``, ``"MOLTBOT"``, etc.
    article_date : str, optional
        ISO-format date of the article when known.
    url : str
        URL of the original source (for provenance tracking).

    Returns
    -------
    list[dict]
        One observation dict per detected signal.  Each has:
        ``type``, ``signal``, ``source_type``, ``evidence_strength``,
        ``corroboration``, ``keyword_hits``, ``origin_id``,
        ``source``, ``url``, ``timestamp``, ``excerpt``.

        ``origin_id`` is a content-based fingerprint so that 5 websites
        copying the same statement count as 1 observation, not 5.
    """
    if not article_text or not article_text.strip():
        return []

    text = article_text.lower()
    crawl_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    normalized_article_date = str(article_date or "").strip()
    if normalized_article_date and len(normalized_article_date) == 10:
        normalized_article_date = f"{normalized_article_date}T12:00:00Z"
    reliability = SOURCE_RELIABILITY.get(source_type.upper(), 0.40)

    # Deduplicate: only emit each signal code once per article
    seen: Dict[str, Dict[str, Any]] = {}

    for keyword, signal_code in KEYWORD_SIGNALS.items():
        if keyword in text:
            if signal_code in seen:
                # Multiple keywords for same signal → boost slightly
                seen[signal_code]["_keyword_confidence"] = min(
                    seen[signal_code]["_keyword_confidence"] + 0.05, 0.85
                )
                seen[signal_code]["keyword_hits"] += 1
            else:
                excerpt = article_text[:200].strip()
                seen[signal_code] = {
                    "type":              "observation",
                    "signal":            signal_code,
                    "source_type":       source_type.upper(),
                    "_keyword_confidence": _BASE_KEYWORD_CONFIDENCE,
                    "keyword_hits":      1,
                    "corroboration":     1,      # single source = 1
                    "origin_id":         _compute_origin_id(signal_code, excerpt),
                    "source":            source_type,
                    "url":               url,
                    "timestamp":         normalized_article_date,
                    "crawl_timestamp":   crawl_iso,
                    "date_source":       "article_date" if normalized_article_date else "unknown",
                    "date_confidence":   0.75 if normalized_article_date else 0.20,
                    "event_confidence":  0.55,
                    "excerpt":           excerpt,
                }

    # Compute evidence_strength and finalize
    results = []
    for obs in seen.values():
        keyword_conf = obs.pop("_keyword_confidence")
        # evidence_strength = keyword confidence ONLY (raw perception strength)
        # Source reliability is NOT baked in here — that's the Belief
        # Accumulator's job.  This separation is critical:
        #   assimilator → "how clearly did I see something?"
        #   accumulator → "how much should I trust this source?"
        #
        # Base hit: 0.50, two keywords: 0.55, three: 0.60, etc.
        # A GOV source and OSINT source both produce ~0.50 evidence_strength
        # for the same text — the DIFFERENCE is in source_type, which the
        # accumulator weights differently.
        obs["evidence_strength"] = round(keyword_conf, 4)
        results.append(obs)
        logger.debug(
            "Observation: %s (strength=%.3f, hits=%d, source=%s)",
            obs["signal"], obs["evidence_strength"],
            obs["keyword_hits"], source_type,
        )

    if results:
        logger.info(
            "Evidence assimilator: %d observation(s) from %s (%d chars)",
            len(results), source_type, len(article_text),
        )

    return results


# ── Legacy compatibility shim ───────────────────────────────────────
# extract_signals() is the old API used by collection_bridge.
# It wraps extract_observations() and adds the fields the bridge expects.

def extract_signals(
    article_text: str,
    source: str = "OSINT",
    article_date: Optional[str] = None,
    url: str = "",
) -> List[Dict[str, Any]]:
    """
    Legacy wrapper — calls extract_observations() then maps output
    to the old signal dict format for backward compatibility.

    New code should use ``extract_observations()`` directly.
    """
    observations = extract_observations(
        article_text, source_type=source,
        article_date=article_date, url=url,
    )
    signals = []
    for obs in observations:
        src_reliability = SOURCE_RELIABILITY.get(obs["source_type"], 0.40)
        signals.append({
            "signal":      obs["signal"],
            "confidence":  obs["evidence_strength"] * src_reliability,
            "recency":     0.95 if str(obs.get("timestamp", "") or "").strip() else 0.20,
            "reliability": src_reliability,
            "source":      obs["source"],
            "timestamp":   obs["timestamp"],
            "url":         obs.get("url", ""),
            # Carry observation metadata through for downstream use
            "_observation": obs,
        })
    return signals


def extract_observations_batch(
    articles: List[Dict[str, Any]],
    default_source: str = "MOLTBOT",
) -> List[Dict[str, Any]]:
    """
    Process multiple articles and return observations grouped by signal.

    Corroboration is computed across articles: if two independent articles
    both mention ``SIG_MIL_MOBILIZATION``, the merged observation has
    ``corroboration=2`` and boosted ``evidence_strength``.

    Each article dict should have at least ``"content"`` (str).
    Optional keys: ``"source"``, ``"date"``, ``"url"``.
    """
    # Group observations by signal code
    by_signal: Dict[str, List[Dict[str, Any]]] = {}

    for article in articles:
        content = article.get("content") or article.get("text") or ""
        source = article.get("source", default_source)
        date = article.get("date") or article.get("published")
        url = article.get("url", "")

        observations = extract_observations(
            content, source_type=source,
            article_date=date, url=url,
        )

        for obs in observations:
            code = obs["signal"]
            if code not in by_signal:
                by_signal[code] = []
            by_signal[code].append(obs)

    # Merge: compute corroboration and combined evidence_strength
    merged: List[Dict[str, Any]] = []
    for signal_code, obs_list in by_signal.items():
        # Use the strongest observation as base
        best = max(obs_list, key=lambda o: o["evidence_strength"])
        corroboration = len(obs_list)

        # Combined strength: sum of individual strengths, capped at 0.85
        # (can never reach 1.0 from OSINT alone — requires dataset/sensor)
        combined_strength = min(
            sum(o["evidence_strength"] for o in obs_list),
            0.85,
        )

        # Collect all unique sources
        sources = list({o["source"] for o in obs_list})

        merged.append({
            "type":              "observation",
            "signal":            signal_code,
            "source_type":       best["source_type"],
            "evidence_strength": round(combined_strength, 4),
            "corroboration":     corroboration,
            "keyword_hits":      sum(o["keyword_hits"] for o in obs_list),
            "source":            ", ".join(sources),
            "sources":           sources,
            "url":               best.get("url", ""),
            "timestamp":         best["timestamp"],
            "excerpt":           best.get("excerpt", ""),
        })

    logger.info(
        "Batch assimilation: %d article(s) → %d observation(s), "
        "corroboration range [%d, %d]",
        len(articles), len(merged),
        min((m["corroboration"] for m in merged), default=0),
        max((m["corroboration"] for m in merged), default=0),
    )
    return merged


# ── Legacy batch compat ─────────────────────────────────────────────
extract_signals_batch = extract_observations_batch


__all__ = [
    "KEYWORD_SIGNALS",
    "SOURCE_RELIABILITY",
    "extract_observations",
    "extract_observations_batch",
    "extract_signals",
    "extract_signals_batch",
]
