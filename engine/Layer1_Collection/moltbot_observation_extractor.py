"""
MoltBot Observation Extractor — Pattern-based signal detection
===============================================================

This module does NOT interpret meaning.
It only detects observable evidence patterns in article text.

Input:  raw article text + URL
Output: structured observation dicts (same format as GDELT sensor)

The patterns are exact, mechanical, and domain-specific.
No LLM, no reasoning, no inference — just pattern matching.
"""

from __future__ import annotations

import re
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from engine.Layer1_Collection.sensors.event_classifier import (
    classify_eventness,
    extract_headline,
    get_canonical_publisher,
)

logger = logging.getLogger("Layer1.sensors.moltbot_extractor")


# =====================================================================
# Signal → Observable Patterns (regex, case-insensitive)
# =====================================================================
# Each pattern is a concrete, specific phrase that an article would
# contain if the corresponding real-world activity occurred.
#
# These are NOT analytical categories — they are literal traces
# of observable events that reporters write about.
# =====================================================================

PATTERNS: Dict[str, List[str]] = {

    # ── Military / Force ──────────────────────────────────────────
    "SIG_FORCE_POSTURE": [
        r"military\s+exercise",
        r"troop\s+deployment",
        r"naval\s+drill",
        r"air\s+defense\s+system",
        r"airbase\s+activation",
        r"naval\s+deployment",
        r"missile\s+battery",
        r"force\s+readiness",
        r"military\s+drill",
        r"combat\s+readiness",
        r"forward\s+deploy",
        r"military\s+maneuver",
        r"show\s+of\s+force",
        r"military\s+buildup",
        r"repositioned?\s+(?:troops|forces|units)",
        r"joint\s+(?:exercise|drill|maneuver)",
        r"carrier\s+strike\s+group",
        r"amphibious\s+(?:exercise|operation)",
    ],

    "SIG_MIL_ESCALATION": [
        r"missile\s+(?:test|launch|strike|fire)",
        r"rocket\s+attack",
        r"airstrike",
        r"air\s+strike",
        r"bombing\s+(?:campaign|raid|run)",
        r"artillery\s+(?:barrage|strike|fire)",
        r"military\s+escalation",
        r"armed\s+(?:conflict|clash)",
        r"cross[- ]?border\s+(?:attack|shelling|strike)",
        r"ballistic\s+missile",
        r"cruise\s+missile",
        r"drone\s+(?:strike|attack)",
        r"exchange\s+of\s+fire",
        r"retaliatory\s+(?:strike|attack)",
        r"military\s+offensive",
        r"ground\s+(?:invasion|incursion|offensive)",
        r"shell(?:ing|ed)\s+(?:positions?|territory|border)",
    ],

    "SIG_MIL_MOBILIZATION": [
        r"(?:general|partial)\s+mobilization",
        r"reservists?\s+(?:called|activated|deployed)",
        r"national\s+guard\s+(?:deployed|activated)",
        r"martial\s+law",
        r"emergency\s+(?:mobilization|deployment)",
        r"war\s+footing",
    ],

    # ── Cyber ─────────────────────────────────────────────────────
    "SIG_CYBER_ACTIVITY": [
        r"cyber\s*(?:attack|offensive|operation|campaign)",
        r"hack(?:ing|ed|ers?)\s+(?:attack|campaign|group)",
        r"APT\s*(?:group|campaign|\d+)",
        r"ransomware\s+attack",
        r"data\s+breach",
        r"cyber\s+espionage",
        r"critical\s+infrastructure\s+(?:attack|breach|hack)",
        r"DDoS\s+attack",
        r"malware\s+(?:campaign|attack|deployment)",
        r"state[- ]?sponsored\s+(?:hack|cyber)",
        r"zero[- ]?day\s+(?:exploit|vulnerability|attack)",
    ],

    # ── Diplomacy / Hostility ─────────────────────────────────────
    "SIG_DIP_HOSTILITY": [
        r"ambassador\s+(?:recalled|expelled|summoned)",
        r"diplomatic\s+(?:expulsion|recall|row|crisis|incident)",
        r"embassy\s+(?:closed|shuttered|evacuated)",
        r"severed?\s+(?:diplomatic|relations)",
        r"persona\s+non\s+grata",
        r"downgraded?\s+(?:diplomatic|relations)",
        r"hostile\s+(?:rhetoric|statement)",
        r"threat(?:ened|s)\s+(?:war|retaliation|strike|attack)",
    ],

    "SIG_DIPLOMACY_ACTIVE": [
        r"peace\s+(?:talks|negotiations|agreement|process|deal)",
        r"ceasefire\s+(?:agreement|talks|negotiation|deal)",
        r"diplomatic\s+(?:summit|talks|meeting|dialogue|breakthrough)",
        r"(?:bilateral|multilateral)\s+(?:talks|summit|agreement)",
        r"normalized?\s+(?:relations|ties)",
        r"mediation\s+(?:efforts?|talks)",
        r"(?:signed|agreed)\s+(?:treaty|accord|pact|deal)",
    ],

    "SIG_NEGOTIATION_BREAKDOWN": [
        r"talks?\s+(?:collapsed?|broke\s+down|failed|suspended|stalled)",
        r"negotiation[s]?\s+(?:collapsed?|broke\s+down|failed|suspended)",
        r"walked?\s+out\s+(?:of|on)\s+(?:talks|negotiations)",
        r"diplomatic\s+(?:impasse|deadlock|stalemate)",
        r"deal\s+(?:collapsed?|fell\s+apart|failed)",
    ],

    # ── Internal Stability ────────────────────────────────────────
    # Split into 3 subtypes for predictive accuracy:
    #   PUBLIC_PROTEST  — low relevance for escalation (citizens)
    #   ELITE_FRACTURE  — high relevance (regime cracks)
    #   MILITARY_DEFECTION — critical (loss of coercive control)
    # The generic SIG_INTERNAL_INSTABILITY still catches broad unrest.

    "SIG_INTERNAL_INSTABILITY": [
        r"political\s+(?:crisis|turmoil|instability|unrest)",
        r"state\s+of\s+emergency(?:\s+declared)?",
        r"curfew\s+(?:imposed|declared|enforced)",
        r"opposition\s+(?:arrested|crackdown|suppressed)",
        r"internet\s+(?:shutdown|blackout|cut)",
    ],

    "SIG_PUBLIC_PROTEST": [
        r"protests?\s+(?:erupted?|broke\s+out|clashed?|swept)",
        r"civil\s+unrest",
        r"riot\s+police\s+(?:deployed|clashed|fired)",
        r"mass\s+(?:demonstrations?|protests?|uprising)",
        r"(?:violent|deadly)\s+(?:protests?|clashes?)",
        r"crackdown\s+(?:on|against)\s+(?:protest|dissent|opposition)",
        r"anti[- ]?government\s+(?:protests?|demonstrations?|rallies?)",
    ],

    "SIG_ELITE_FRACTURE": [
        r"(?:senior|top|key)\s+(?:official|minister|general|commander)\s+(?:resigned|defected|fired|dismissed|sacked)",
        r"power\s+(?:struggle|grab|vacuum)",
        r"(?:cabinet|government)\s+(?:reshuffle|shakeup|purge)",
        r"(?:ruling|governing)\s+(?:party|coalition)\s+(?:split|fractured|divided)",
        r"(?:president|prime\s+minister|leader)\s+(?:ousted|removed|impeached)",
        r"(?:elite|factional|internal)\s+(?:split|rivalry|infighting|discord)",
        r"succession\s+(?:crisis|struggle|battle)",
    ],

    "SIG_MILITARY_DEFECTION": [
        r"(?:military|army|general|commander|officer)\s+(?:defect|defected|defection|mutiny|mutinied)",
        r"(?:troops?|soldiers?|units?)\s+(?:defect|refused|mutinied|rebelled|switched\s+sides)",
        r"(?:coup|putsch)\s+(?:attempt|underway|rumored|foiled|d'etat)",
        r"(?:military|army)\s+(?:revolt|rebellion|uprising|takeover)",
        r"(?:lost|losing)\s+(?:control|loyalty)\s+(?:of|over)\s+(?:military|armed\s+forces|troops)",
    ],

    # ── Economic / Sanctions ──────────────────────────────────────
    "SIG_ECON_PRESSURE": [
        r"sanctions?\s+(?:imposed|tightened|expanded|escalated)",
        r"economic\s+(?:pressure|sanctions|restrictions|penalty|penalties)",
        r"trade\s+(?:restrictions?|embargo|ban|sanctions)",
        r"asset\s+(?:freeze|seizure|frozen)",
        r"(?:oil|energy|gas)\s+(?:embargo|sanctions?|restriction)",
        r"(?:import|export)\s+(?:ban|restriction|controls?)",
        r"financial\s+(?:sanctions?|restrictions?|blacklist)",
        r"OFAC\s+(?:designation|sanctions?|listing)",
        r"treasury\s+(?:sanctions?|designation)",
    ],

    "SIG_ECO_SANCTIONS_ACTIVE": [
        r"sanctions?\s+(?:enforced|active|in\s+(?:place|effect))",
        r"sanctions?\s+(?:compliance|violation|evasion|circumvention)",
        r"secondary\s+sanctions",
        r"sanctions?\s+(?:waiver|exemption|relief)",
        r"snapback\s+sanctions",
    ],

    # ── Coercion / Illegal ────────────────────────────────────────
    "SIG_COERCIVE_PRESSURE": [
        r"(?:illegal|unlawful)\s+(?:coercion|detention|seizure|occupation)",
        r"human\s+rights?\s+(?:violation|abuse|crackdown)",
        r"(?:forced|arbitrary)\s+(?:detention|arrest|disappearance)",
        r"war\s+crime",
        r"ethnic\s+cleansing",
        r"genocide",
        r"hostage\s+(?:taking|crisis|situation)",
        r"(?:extrajudicial|summary)\s+(?:killing|execution)",
    ],

    "SIG_COERCIVE_BARGAINING": [
        r"ultimatum\s+(?:issued|delivered|given)",
        r"coercive\s+(?:diplomacy|bargaining|pressure)",
        r"(?:economic|military)\s+(?:blackmail|extortion|coercion)",
        r"maximum\s+pressure\s+(?:campaign|policy|strategy)",
    ],

    # ── WMD / Nuclear ─────────────────────────────────────────────
    "SIG_WMD_RISK": [
        r"(?:nuclear|uranium)\s+(?:enrichment|program|weapon|test|warhead)",
        r"(?:chemical|biological)\s+(?:weapon|agent|attack)",
        r"(?:IAEA|safeguards?)\s+(?:inspection|violation|breach)",
        r"(?:centrifuge|yellowcake|plutonium|highly\s+enriched)",
        r"weapons?\s+of\s+mass\s+destruction",
        r"WMD\s+(?:program|capability|proliferation)",
        r"(?:nuclear|atomic)\s+(?:test|detonation|explosion)",
    ],

    # ── Alliance / Geopolitical ───────────────────────────────────
    "SIG_ALLIANCE_ACTIVATION": [
        r"(?:mutual|collective)\s+(?:defense|security)\s+(?:pact|treaty|agreement|invoked)",
        r"(?:NATO|alliance)\s+(?:article\s+5|activated|invoked|deployed)",
        r"(?:allied|coalition)\s+(?:forces?|troops?)\s+(?:deployed|sent|dispatched)",
        r"military\s+(?:alliance|pact|coalition)\s+(?:formed|activated)",
    ],

    "SIG_ALLIANCE_SHIFT": [
        r"(?:alliance|partnership)\s+(?:realignment|shift|pivot|rebalance)",
        r"(?:broke|breaking|withdrawn?)\s+(?:from|with)\s+(?:alliance|pact|treaty)",
        r"(?:new|strategic)\s+(?:partnership|alliance|pact)\s+(?:signed|formed|announced)",
        r"(?:arms|defense)\s+(?:deal|agreement|sale|transfer)\s+(?:signed|announced|approved)",
    ],

    # ── Deception ─────────────────────────────────────────────────
    "SIG_DECEPTION_ACTIVITY": [
        r"(?:disinformation|propaganda)\s+campaign",
        r"(?:fake|fabricated|false)\s+(?:news|intelligence|evidence|flag)",
        r"(?:concealment|cover[- ]?up)\s+(?:operation|activity)",
        r"(?:information|influence)\s+(?:operation|warfare|campaign)",
        r"(?:deny|denied|denying)\s+(?:involvement|responsibility|attack)",
    ],
}


# =====================================================================
# Evidence strength by signal type
# =====================================================================

_SIGNAL_BASE_STRENGTH: Dict[str, float] = {
    "SIG_MIL_ESCALATION":      0.70,
    "SIG_FORCE_POSTURE":       0.55,
    "SIG_MIL_MOBILIZATION":    0.65,
    "SIG_CYBER_ACTIVITY":      0.50,
    "SIG_DIP_HOSTILITY":       0.50,
    "SIG_DIPLOMACY_ACTIVE":    0.50,
    "SIG_NEGOTIATION_BREAKDOWN": 0.55,
    "SIG_INTERNAL_INSTABILITY": 0.50,
    "SIG_ECON_PRESSURE":       0.50,
    "SIG_ECO_SANCTIONS_ACTIVE": 0.50,
    "SIG_COERCIVE_PRESSURE":   0.55,
    "SIG_COERCIVE_BARGAINING": 0.50,
    "SIG_WMD_RISK":            0.70,
    "SIG_ALLIANCE_ACTIVATION": 0.55,
    "SIG_ALLIANCE_SHIFT":      0.50,
    "SIG_DECEPTION_ACTIVITY":  0.45,
    # Instability subtypes — weighted by predictive value
    "SIG_PUBLIC_PROTEST":      0.30,   # low — citizens protesting != regime risk
    "SIG_ELITE_FRACTURE":      0.70,   # high — regime cracks matter
    "SIG_MILITARY_DEFECTION":  0.85,   # critical — loss of coercive monopoly
}

_DEFAULT_STRENGTH: float = 0.50

# =====================================================================
# Date confidence by extraction strategy
# (mirrors DATE_CONFIDENCE in moltbot_sensor.py)
# =====================================================================

_DATE_CONFIDENCE: Dict[str, float] = {
    "og_meta":      1.00,
    "meta_name":    0.90,
    "html5_time":   0.90,
    "schema_org":   1.00,
    "url_pattern":  0.70,
    "prose_text":   0.50,
    "crawl_time":   0.30,
}


# =====================================================================
# Core extraction function
# =====================================================================

def extract_observations(
    text: str,
    url: str = "",
    source_type: str = "OSINT",
    target_signals: Optional[List[str]] = None,
    publish_date: str = "",
    date_strategy: str = "",
    headline: str = "",
) -> List[Dict[str, Any]]:
    """
    Extract signal observations from article text using pattern matching.

    Parameters
    ----------
    text : str
        The raw article text to scan.
    url : str
        Source URL for provenance tracking.
    source_type : str
        Source classification (default: "OSINT").
    target_signals : list[str], optional
        If provided, only scan for these signals (performance optimization).
        If None, scan all patterns.
    publish_date : str, optional
        ISO "YYYY-MM-DD" extracted from HTML metadata by the Event Time
        Resolver.  When provided, this becomes the observation timestamp
        instead of crawl-time.  This is critical for accurate temporal
        memory — recency must reflect *when the event occurred*, not
        when the article was scraped.
    date_strategy : str, optional
        The extraction strategy that found the publish date (e.g.
        "og_meta", "schema_org", "url_pattern", "prose_text").
        When empty and publish_date is set, defaults to "html_meta"
        for backward compatibility.

    Returns
    -------
    list[dict]
        Observation dicts in the SAME format as GDELT sensor output:
        {type, signal, source_type, evidence_strength, corroboration,
         keyword_hits, origin_id, source, url, timestamp, excerpt,
         date_source, date_confidence}
    """
    if not text or len(text) < 20:
        return []

    observations: List[Dict[str, Any]] = []
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Determine the authoritative timestamp for this article.
    # If the Event Time Resolver extracted a real publish_date from
    # HTML metadata, use it.  Otherwise fall back to crawl-time.
    if publish_date:
        # Convert "YYYY-MM-DD" → full ISO timestamp at noon UTC
        _ts = f"{publish_date}T12:00:00Z"
        # Use the specific strategy tag if provided, else generic "html_meta"
        _date_source = date_strategy if date_strategy else "html_meta"
    else:
        _ts = ""
        _date_source = "crawl_time"

    # Compute date confidence from strategy tag
    _date_conf = _DATE_CONFIDENCE.get(_date_source, 0.30)

    # ── Event classification ─────────────────────────────────────
    # Determine if this is hard news vs commentary/opinion.
    # Commentary articles get low event_confidence, suppressing
    # their weight in the belief accumulator.
    try:
        _headline = headline or extract_headline(text)
        _event_type, _event_conf = classify_eventness(text, _headline, url)
    except Exception:
        _event_type, _event_conf = "context", 0.50

    # ── Publisher domain extraction ──────────────────────────────
    _publisher = get_canonical_publisher(url)

    # Which signals to check
    scan_signals = target_signals if target_signals else list(PATTERNS.keys())

    for signal in scan_signals:
        patterns = PATTERNS.get(signal, [])
        if not patterns:
            continue

        hits: List[str] = []
        excerpts: List[str] = []

        for pattern in patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            if matches:
                hits.append(pattern)
                # Extract context around first match (snippet)
                for m in matches[:1]:
                    start = max(0, m.start() - 60)
                    end = min(len(text), m.end() + 120)
                    snippet = text[start:end].strip()
                    # Clean whitespace
                    snippet = re.sub(r'\s+', ' ', snippet)
                    excerpts.append(snippet)

        if not hits:
            continue

        # Build excerpt from matched snippets
        excerpt_text = " | ".join(excerpts[:3])
        if len(excerpt_text) > 300:
            excerpt_text = excerpt_text[:297] + "..."

        # Evidence strength: base + bonus for multiple pattern hits
        base = _SIGNAL_BASE_STRENGTH.get(signal, _DEFAULT_STRENGTH)
        multi_hit_boost = min(0.15, (len(hits) - 1) * 0.05)
        strength = min(0.85, base + multi_hit_boost)

        # Stable origin ID for deduplication
        origin_id = _compute_origin_id(url, signal)

        obs = {
            "type": "observation",
            "signal": signal,
            "source_type": source_type,
            "evidence_strength": round(strength, 4),
            "corroboration": 1,  # single source — corroboration comes from accumulator
            "keyword_hits": len(hits),
            "origin_id": origin_id,
            "source": "MOLTBOT",
            "url": url,
            "timestamp": _ts,
            "crawl_timestamp": now_iso,
            "date_source": _date_source,
            "date_confidence": _date_conf,
            "event_type": _event_type,
            "event_confidence": _event_conf,
            "publisher_domain": _publisher,
            "excerpt": f"[OSINT] {excerpt_text}",
        }
        observations.append(obs)

    if observations:
        logger.info(
            "[EXTRACTOR] %d signal(s) from %s: %s",
            len(observations),
            url[:60] if url else "(no url)",
            ", ".join(o["signal"] for o in observations),
        )

    return observations


def extract_observations_targeted(
    text: str,
    signal_code: str,
    url: str = "",
    source_type: str = "OSINT",
) -> List[Dict[str, Any]]:
    """
    Extract observations for a SINGLE target signal only.

    This is the fast path for directed collection — when we already know
    what signal we're looking for, only scan those patterns.
    """
    return extract_observations(
        text=text,
        url=url,
        source_type=source_type,
        target_signals=[signal_code],
    )


# =====================================================================
# Helpers
# =====================================================================

def _compute_origin_id(url: str, signal: str) -> str:
    """Stable dedup key from URL + signal."""
    raw = f"moltbot:{url}:{signal}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()[:16]


def get_supported_signals() -> List[str]:
    """Return list of all signals the extractor can detect."""
    return list(PATTERNS.keys())


__all__ = [
    "PATTERNS",
    "extract_observations",
    "extract_observations_targeted",
    "get_supported_signals",
]
