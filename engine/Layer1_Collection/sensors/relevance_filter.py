"""
Relevance Filter — Stop Wrong-Country Articles
================================================

Intelligence collection systems must validate that fetched articles
actually discuss the TARGET country, not unrelated geographies that
happen to share keywords.

Example problem (from production logs):
    Query: "Iran nuclear escalation"
    Article: "India protests erupt across major cities"
    → MoltBot extracted SIG_INTERNAL_INSTABILITY for *Iran*

This module sits BETWEEN ``fetch_article()`` and ``extract_observations()``.
It scores how relevant an article is to the target country/actor and
rejects articles below a configurable threshold.

Scoring:
    1. Count mentions of target country + aliases in full text
    2. Check if target appears in first 500 chars (headline proximity)
    3. Penalise if a DIFFERENT country appears more often (actor confusion)
    4. Combine into a 0–1 relevance score

Usage:
    from engine.Layer1_Collection.sensors.relevance_filter import score_relevance

    relevance = score_relevance(article_text, "IRN")
    if relevance < RELEVANCE_THRESHOLD:
        logger.info("[RELEVANCE] Rejected: %s (score=%.2f)", url, relevance)
        continue
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from Utils.country_normalization import (
    build_country_alias_index,
    resolve_country_iso,
)

logger = logging.getLogger("Layer1.sensors.relevance_filter")


# =====================================================================
# Default rejection threshold
# =====================================================================
# Articles below this score are discarded before signal extraction.
# 0.45 balances precision (no wrong-country) vs recall (keep tangential).
RELEVANCE_THRESHOLD = 0.45


# =====================================================================
# Country alias map — ISO-3 → list of name variants, leaders,
# key cities, organisations, and demonyms.
# =====================================================================

COUNTRY_ALIASES: Dict[str, List[str]] = {
    "IRN": [
        "Iran", "Iranian", "Tehran", "IRGC", "Isfahan", "Khamenei",
        "Raisi", "Persian Gulf", "Hormuz", "Natanz", "Fordow",
        "Bushehr", "Qom", "Shiraz", "Mashad", "Rouhani", "Zarif",
        "Quds Force", "Hezbollah",
    ],
    "USA": [
        "United States", "American", "Washington", "Pentagon",
        "White House", "Biden", "Trump", "Congress", "U.S.",
        "US military", "CENTCOM", "State Department", "CIA",
        "NSA", "USAF", "US Navy", "DoD",
    ],
    "CHN": [
        "China", "Chinese", "Beijing", "PLA", "Xi Jinping",
        "PRC", "South China Sea", "Taiwan Strait", "CCP",
        "People's Liberation Army", "Shanghai", "Guangdong",
        "CPC", "Zhongnanhai", "PLAN",
    ],
    "RUS": [
        "Russia", "Russian", "Moscow", "Kremlin", "Putin",
        "Lavrov", "Shoigu", "Gerasimov", "Black Sea",
        "Baltic", "Kaliningrad", "FSB", "GRU",
        "Wagner", "Duma", "Arctic",
    ],
    "IND": [
        "India", "Indian", "New Delhi", "Modi",
        "Rajnath Singh", "Jaishankar", "Kashmir",
        "Line of Control", "Mumbai", "Ladakh",
        "Indian Ocean", "RAW", "DRDO",
    ],
    "PAK": [
        "Pakistan", "Pakistani", "Islamabad", "Rawalpindi",
        "Karachi", "ISI", "Balochistan", "Punjab",
        "Line of Control", "Kashmir",
    ],
    "PRK": [
        "North Korea", "DPRK", "Pyongyang", "Kim Jong Un",
        "Korean People's Army", "Yongbyon",
        "38th parallel", "Kim regime",
    ],
    "KOR": [
        "South Korea", "Seoul", "ROK", "Korean",
        "Yoon Suk Yeol", "Blue House",
    ],
    "ISR": [
        "Israel", "Israeli", "Tel Aviv", "Jerusalem",
        "Netanyahu", "IDF", "Mossad", "Shin Bet",
        "Gaza", "West Bank", "Knesset", "Galant",
    ],
    "UKR": [
        "Ukraine", "Ukrainian", "Kyiv", "Zelensky",
        "Donbas", "Crimea", "Kherson", "Zaporizhzhia",
        "Odessa", "Bakhmut",
    ],
    "SAU": [
        "Saudi Arabia", "Saudi", "Riyadh", "MBS",
        "Mohammed bin Salman", "ARAMCO", "Jeddah",
    ],
    "TUR": [
        "Turkey", "Turkish", "Ankara", "Erdogan",
        "Istanbul", "Bosphorus", "Turkiye",
    ],
    "TWN": [
        "Taiwan", "Taiwanese", "Taipei", "Tsai Ing-wen",
        "ROC", "Strait", "Formosa",
    ],
}

_COUNTRY_ALIAS_INDEX = build_country_alias_index(COUNTRY_ALIASES)

# Common confusable pairs — countries whose keywords overlap
_CONFUSABLE_PAIRS: Dict[str, List[str]] = {
    "IRN": ["IND", "IRQ"],    # Iran ↔ India / Iraq
    "IND": ["IRN", "IDN"],    # India ↔ Iran / Indonesia
    "PRK": ["KOR"],           # North Korea ↔ South Korea
    "KOR": ["PRK"],
    "PAK": ["IND"],
    "ISR": ["IRN"],
}


# =====================================================================
# Core scoring function
# =====================================================================

def score_relevance(
    article_text: str,
    country_iso: str,
    target_aliases: Optional[List[str]] = None,
    headline: str = "",
) -> float:
    """
    Score how relevant an article is to a target country/actor.

    Parameters
    ----------
    article_text : str
        Full article text (up to 10 000 chars).
    country_iso : str
        Target country reference. ISO-3 is preferred, but full country
        names and known aliases are also accepted.
    target_aliases : list[str], optional
        Override alias list.  If None, uses built-in COUNTRY_ALIASES.

    Returns
    -------
    float
        Relevance score 0.0 – 1.0.
        Recommended threshold: ``RELEVANCE_THRESHOLD`` (0.45).
    """
    if not article_text or not country_iso:
        return 0.0

    raw_country = country_iso.strip()
    iso = resolve_country_iso(raw_country, alias_index=_COUNTRY_ALIAS_INDEX)
    log_token = iso or raw_country.upper()
    aliases = target_aliases or COUNTRY_ALIASES.get(iso, [])

    if not aliases:
        # Unknown country — can't filter, pass through
        logger.debug("[RELEVANCE] No aliases for %s — skipping filter", log_token)
        return 1.0

    text_lower = article_text.lower()
    text_head = text_lower[:500]    # headline / first paragraph

    # ── 1. Count target mentions ─────────────────────────────────
    target_mentions = 0
    for alias in aliases:
        # Case-insensitive word-boundary match
        pattern = re.compile(r"\b" + re.escape(alias) + r"\b", re.IGNORECASE)
        target_mentions += len(pattern.findall(article_text))

    # ── 2. Headline proximity bonus ──────────────────────────────
    headline_bonus = 0.0
    for alias in aliases:
        if alias.lower() in text_head:
            headline_bonus = 1.0
            break

    # ── 3. Confusable country penalty ────────────────────────────
    # If a confusable country (e.g. India for Iran) is mentioned
    # MORE than the target, apply a penalty.
    confusable_mentions = 0
    confusable_isos = _CONFUSABLE_PAIRS.get(iso, [])
    for conf_iso in confusable_isos:
        conf_aliases = COUNTRY_ALIASES.get(conf_iso, [])
        for alias in conf_aliases:
            pattern = re.compile(r"\b" + re.escape(alias) + r"\b", re.IGNORECASE)
            confusable_mentions += len(pattern.findall(article_text))

    confusion_penalty = 0.0
    if confusable_mentions > target_mentions and target_mentions > 0:
        # Confusable country is MORE prominent — suspect wrong-country
        confusion_penalty = min(0.40, (confusable_mentions - target_mentions) * 0.05)
    elif confusable_mentions > 0 and target_mentions == 0:
        # Target not mentioned at all but confusable is — almost certainly wrong
        confusion_penalty = 0.60

    # ── 4. Primary actor detection ───────────────────────────────
    # "China warns US about Iran war" — primary actor is China.
    # If target country is NOT the primary actor, apply 50% penalty.
    primary_actor_penalty = 0.0
    _headline_text = headline.lower() if headline else text_head

    if _headline_text and target_mentions > 0:
        # Check if a DIFFERENT country's alias appears BEFORE target
        # in the headline — that country is likely the primary actor.
        first_target_pos = len(_headline_text)
        for alias in aliases:
            pos = _headline_text.find(alias.lower())
            if pos >= 0 and pos < first_target_pos:
                first_target_pos = pos

        # Check all other country aliases for earlier appearance
        for other_iso, other_aliases in COUNTRY_ALIASES.items():
            if other_iso == iso:
                continue
            for other_alias in other_aliases:
                other_pos = _headline_text.find(other_alias.lower())
                if 0 <= other_pos < first_target_pos:
                    # Another country appears before target in headline
                    primary_actor_penalty = 0.25
                    logger.debug(
                        "[RELEVANCE] Primary actor penalty: '%s' appears "
                        "before target %s in headline",
                        other_alias, iso,
                    )
                    break
            if primary_actor_penalty > 0:
                break

    # ── 5. Quote-only check ──────────────────────────────────────
    # If target country only appears inside quotes, likely someone
    # TALKING about it, not a direct event. Apply penalty.
    quote_penalty = 0.0
    if target_mentions > 0 and target_mentions <= 3:
        # Check if all mentions are within quotes
        in_quotes = 0
        for alias in aliases:
            # Find mentions inside "..." or '...'
            quoted_pattern = re.compile(
                r'["\u201c][^"\u201d]*\b' + re.escape(alias) + r'\b[^"\u201d]*["\u201d]',
                re.IGNORECASE,
            )
            in_quotes += len(quoted_pattern.findall(article_text))

        if in_quotes >= target_mentions:
            quote_penalty = 0.30
            logger.debug(
                "[RELEVANCE] Quote-only penalty: %s only in quotes for %s",
                aliases[0] if aliases else iso, iso,
            )

    # ── 6. Combine into score ────────────────────────────────────
    # Formula: mention_score + headline_bonus - penalties
    # mention_score: saturates at ~10 mentions
    mention_score = min(1.0, target_mentions * 0.10)
    headline_component = headline_bonus * 0.30

    raw_score = (
        mention_score + headline_component
        - confusion_penalty - primary_actor_penalty - quote_penalty
    )
    score = max(0.0, min(1.0, raw_score))

    if score < RELEVANCE_THRESHOLD:
        logger.debug(
            "[RELEVANCE] LOW: %.2f (mentions=%d, headline=%.1f, "
            "confusable=%d, conf_penalty=%.2f, actor_penalty=%.2f, "
            "quote_penalty=%.2f) for %s",
            score, target_mentions, headline_bonus,
            confusable_mentions, confusion_penalty,
            primary_actor_penalty, quote_penalty, iso,
        )

    return round(score, 3)


def get_aliases(country_iso: str) -> List[str]:
    """Return alias list for a country reference."""
    iso = resolve_country_iso(country_iso, alias_index=_COUNTRY_ALIAS_INDEX)
    return COUNTRY_ALIASES.get(iso, [])


__all__ = [
    "score_relevance",
    "get_aliases",
    "COUNTRY_ALIASES",
    "RELEVANCE_THRESHOLD",
]
