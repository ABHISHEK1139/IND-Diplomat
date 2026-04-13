"""
Event Classifier — Eventness Detection & Credibility Filter
=============================================================

Intercepts article text BEFORE it becomes a signal to distinguish
between **hard news events** and **commentary/analysis/opinion**.

The core insight:
    A correctly dated article can still be analytically useless.

Example:
    "Explainer: Iran nuclear program history (2015 deal)"
    - Published today            -> valid date
    - Meta date correct          -> date_confidence = 1.0
    - But NOT a new event        -> should NOT trigger escalation

This module provides:
    - ``classify_eventness()``  — rule-based event vs commentary detection
    - ``extract_headline()``    — pull first-line headline from article text
    - ``extract_domain()``      — publisher domain extraction for corroboration
    - ``get_canonical_publisher()`` — collapse syndication to canonical publisher

Pipeline position::

    fetch_article() -> **event_classifier** -> extract_observations() -> accumulator

Usage::

    from engine.Layer1_Collection.sensors.event_classifier import (
        classify_eventness, extract_domain, get_canonical_publisher,
    )

    event_type, event_conf = classify_eventness(text, headline, url)
    publisher = get_canonical_publisher(url)
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse
from typing import Dict, Tuple

logger = logging.getLogger("Layer1.sensors.event_classifier")


# =====================================================================
# Action verbs — strong indicators of a real-world event
# =====================================================================
# Past-tense / present-perfect verbs that reporters use
# when describing something that HAPPENED, not something being analysed.

_EVENT_VERBS = re.compile(
    r"\b("
    r"said|announced|launched|struck|fired|attacked|signed|deployed|closed|"
    r"invaded|seized|arrested|expelled|recalled|mobilized|sanctioned|"
    r"bombed|shelled|intercepted|captured|raided|tested|detonated|"
    r"assassinated|detained|killed|shot|withdrew|collapsed|declared|"
    r"imposed|resigned|overthrew|surrendered|breached|violated|"
    r"evacuated|blockaded|escalated|retaliated"
    r")\b",
    re.IGNORECASE,
)

# =====================================================================
# Commentary indicators — phrases that signal opinion/analysis
# =====================================================================

_COMMENTARY_KEYWORDS = re.compile(
    r"\b("
    r"analysis|explainer|opinion|what\s+is|history\s+of|column|"
    r"editorial|perspective|commentary|explained|understanding|"
    r"background|primer|overview|deep\s+dive|in\s+(?:context|focus)|"
    r"timeline|recap|guide\s+to|everything\s+you\s+need|"
    r"lessons?\s+(?:from|of|learned)|why\s+(?:it|this)\s+matters|"
    r"could|might|may\s+(?:lead|cause|trigger)|if\s+.+then|"
    r"what\s+(?:if|would|could)|scenario|hypothetical"
    r")\b",
    re.IGNORECASE,
)

# URL path segments that strongly indicate commentary
_COMMENTARY_URL_PATTERNS = re.compile(
    r"(?:opinion|analysis|explainer|editorial|column|blog|podcast|"
    r"review|comment|perspective|feature|magazine|long-read)",
    re.IGNORECASE,
)

# Headline patterns indicating breaking/hard news
_BREAKING_PATTERNS = re.compile(
    r"\b(breaking|just\s+in|update|latest|confirmed|official|"
    r"reports?\s+(?:say|confirm|indicate))\b",
    re.IGNORECASE,
)


# =====================================================================
# Core classification
# =====================================================================

def classify_eventness(
    text: str,
    headline: str = "",
    url: str = "",
) -> Tuple[str, float]:
    """
    Classify an article as EVENT, COMMENTARY, or CONTEXT.

    Parameters
    ----------
    text : str
        Full article text (first ~5000 chars used).
    headline : str
        Article headline / title (if available).
    url : str
        Source URL (path segments checked for opinion/analysis markers).

    Returns
    -------
    tuple[str, float]
        (event_type, event_confidence)
        event_type: "event" | "commentary" | "context"
        event_confidence: 0.0 - 1.0

    Classification logic:
        1. URL path quick-reject (opinion/editorial sections)
        2. Headline quick-reject (explainer/analysis markers)
        3. Verb analysis - count event verbs vs commentary keywords
        4. Breaking news boost
        5. Final decision
    """
    if not text:
        return "context", 0.3

    # Use first 5000 chars for efficiency
    text_sample = text[:5000]
    headline_lower = (headline or "").lower()
    url_lower = (url or "").lower()

    # -- 1. URL path quick-reject --
    if _COMMENTARY_URL_PATTERNS.search(url_lower):
        logger.debug(
            "[EVENT-CLASSIFIER] URL path indicates commentary: %s",
            url[:60],
        )
        return "commentary", 0.20

    # -- 2. Headline quick-reject --
    if headline_lower:
        commentary_in_headline = _COMMENTARY_KEYWORDS.search(headline_lower)
        if commentary_in_headline:
            logger.debug(
                "[EVENT-CLASSIFIER] Headline indicates commentary: '%s'",
                headline[:80],
            )
            return "commentary", 0.25

    # -- 3. Verb & keyword analysis --
    event_verb_matches = _EVENT_VERBS.findall(text_sample)
    commentary_matches = _COMMENTARY_KEYWORDS.findall(text_sample)

    event_verb_count = len(event_verb_matches)
    commentary_count = len(commentary_matches)

    # -- 4. Breaking news boost --
    breaking_in_headline = bool(
        _BREAKING_PATTERNS.search(headline_lower)
    ) if headline_lower else False

    # -- 5. Decision matrix --

    # Strong event: many action verbs, no commentary markers
    if event_verb_count >= 3 and commentary_count == 0:
        conf = min(1.0, 0.85 + (0.05 if breaking_in_headline else 0.0))
        return "event", conf

    # Breaking news override
    if breaking_in_headline and event_verb_count >= 1:
        return "event", 0.90

    # Moderate event: more verbs than commentary
    if event_verb_count >= 2 and event_verb_count > commentary_count:
        return "event", 0.70

    # Mixed: some verbs, some commentary
    if event_verb_count >= 1 and commentary_count >= 1:
        ratio = event_verb_count / max(1, event_verb_count + commentary_count)
        if ratio > 0.6:
            return "event", 0.60
        else:
            return "context", 0.40

    # Dominant commentary
    if commentary_count >= 2 and event_verb_count <= 1:
        return "commentary", 0.25

    # Some event verbs but not dominant
    if event_verb_count >= 1:
        return "context", 0.50

    # No clear signals — default to low-confidence context
    return "context", 0.35


# =====================================================================
# Headline extraction
# =====================================================================

def extract_headline(text: str) -> str:
    """
    Extract the first meaningful line from article text as headline.

    Used when no explicit headline is available from HTML metadata.
    """
    if not text:
        return ""

    for line in text.strip().split("\n"):
        line = line.strip()
        # Skip very short lines (nav items, dates, etc.)
        if len(line) > 20 and not line.startswith("http"):
            return line[:200]

    return text[:200].strip()


# =====================================================================
# Publisher domain extraction
# =====================================================================

# Known syndication networks — these all ultimately source from
# the same wire service and should NOT count as independent publishers.
_WIRE_SYNDICATION: Dict[str, str] = {
    # Reuters syndication
    "reuters.com":          "reuters",
    "uk.reuters.com":       "reuters",
    "in.reuters.com":       "reuters",
    # AP syndication
    "apnews.com":           "ap",
    "hosted.ap.org":        "ap",
    # AFP syndication
    "france24.com":         "afp",
    # Indian media — often carry identical Reuters/AP copy
    "ndtv.com":             "ndtv",
    "timesofindia.indiatimes.com": "toi",
    "hindustantimes.com":   "ht",
    "news18.com":           "news18",
    "republicworld.com":    "republic",
    "thehindu.com":         "thehindu",
    "livemint.com":         "livemint",
    # US media
    "nytimes.com":          "nyt",
    "washingtonpost.com":   "wapo",
    "politico.com":         "politico",
    "cnn.com":              "cnn",
    "foxnews.com":          "fox",
    "bbc.com":              "bbc",
    "bbc.co.uk":            "bbc",
    # Middle East
    "aljazeera.com":        "aljazeera",
    "middleeasteye.net":    "mee",
    "timesofisrael.com":    "toi_il",
    "presstv.ir":           "presstv",
    "irna.ir":              "irna",
    "tasnimnews.com":       "tasnim",
    # Institutional
    "un.org":               "un",
    "iaea.org":             "iaea",
    "sipri.org":            "sipri",
}


def extract_domain(url: str) -> str:
    """
    Extract the canonical publisher domain from a URL.

    Returns the normalised domain (e.g. "reuters.com") which is used
    for publisher independence checks in the belief accumulator.
    """
    if not url:
        return "unknown"
    try:
        domain = urlparse(url).netloc.lower()
        domain = domain.replace("www.", "")
        return domain or "unknown"
    except Exception:
        return "unknown"


def get_canonical_publisher(url: str) -> str:
    """
    Map a URL to its canonical publisher ID.

    This collapses syndication networks: e.g. reuters.com and
    uk.reuters.com both map to "reuters".

    If the domain isn't in the known mapping, the raw domain is used.
    """
    domain = extract_domain(url)
    return _WIRE_SYNDICATION.get(domain, domain)


__all__ = [
    "classify_eventness",
    "extract_headline",
    "extract_domain",
    "get_canonical_publisher",
]
