"""
MoltBot Web Sensor — The System's Eyes on the Open Web
========================================================

MoltBot is NOT a thinker.  It is a **sensor**.

It does NOT understand geopolitics.
It only **detects observable evidence patterns**.

Runtime pipeline (no LLM, no reasoning):
    1. Receive signal codes from curiosity controller
    2. Convert signals → web search queries (mapping table)
    3. Search the web (DuckDuckGo → Bing RSS → fallback)
    4. Fetch articles (requests + BeautifulSoup)
    5. Convert article text → observations (regex pattern matching)
    6. Return structured observation dicts → Belief Accumulator

This module is parallel to gdelt_sensor.py:
    GDELT  = radar   (structured events from coded data)
    MoltBot = camera  (narrative evidence from news articles)

Together they give the system perception.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urljoin, urlparse

logger = logging.getLogger("Layer1.sensors.moltbot")


# =====================================================================
# SIGNAL → SEARCH QUERY MAP
# =====================================================================
# These are concrete, observable phrases that appear in news articles.
# NOT analytical categories.  NOT questions.  NOT intelligence requirements.
#
# When the system says "PIR: SIG_FORCE_POSTURE", it becomes:
#   search("Iran troop deployment")
#   search("Iran military exercise")
#
# No LLM.  Just mapping.
# =====================================================================

SIGNAL_QUERY_MAP: Dict[str, List[str]] = {

    "SIG_FORCE_POSTURE": [
        "troop deployment",
        "military exercise",
        "naval deployment",
        "airbase activation",
        "missile battery repositioned",
        "military buildup",
    ],

    "SIG_MIL_ESCALATION": [
        "missile strike",
        "airstrike attack",
        "military escalation",
        "artillery shelling",
        "drone attack",
        "rocket attack",
    ],

    "SIG_MIL_MOBILIZATION": [
        "military mobilization",
        "reservists called up",
        "martial law declared",
        "troops mobilized",
    ],

    "SIG_CYBER_ACTIVITY": [
        "cyber attack",
        "hacking campaign",
        "critical infrastructure hack",
        "state sponsored cyber",
        "ransomware attack",
    ],

    "SIG_DIP_HOSTILITY": [
        "ambassador expelled",
        "diplomatic crisis",
        "embassy closed",
        "diplomatic relations severed",
        "hostile rhetoric threat",
    ],

    "SIG_DIPLOMACY_ACTIVE": [
        "peace talks",
        "ceasefire agreement",
        "diplomatic summit",
        "bilateral negotiations",
        "peace deal signed",
    ],

    "SIG_NEGOTIATION_BREAKDOWN": [
        "talks collapsed",
        "negotiations suspended",
        "diplomatic talks failed",
        "walked out of talks",
        "deal collapsed",
    ],

    "SIG_INTERNAL_INSTABILITY": [
        "protests erupted",
        "civil unrest",
        "riot police deployed",
        "mass demonstrations",
        "anti government protests",
    ],

    "SIG_ECON_PRESSURE": [
        "sanctions imposed",
        "economic sanctions",
        "trade restrictions",
        "oil embargo",
        "asset freeze",
    ],

    "SIG_ECO_SANCTIONS_ACTIVE": [
        "sanctions enforcement",
        "sanctions compliance",
        "secondary sanctions",
        "sanctions evasion",
    ],

    "SIG_COERCIVE_PRESSURE": [
        "human rights violation",
        "arbitrary detention",
        "war crime",
        "hostage crisis",
    ],

    "SIG_COERCIVE_BARGAINING": [
        "ultimatum issued",
        "maximum pressure",
        "coercive diplomacy",
    ],

    "SIG_WMD_RISK": [
        "nuclear enrichment",
        "uranium enrichment",
        "IAEA inspection",
        "nuclear weapons program",
        "ballistic missile test",
    ],

    "SIG_ALLIANCE_ACTIVATION": [
        "mutual defense pact",
        "alliance activated",
        "coalition forces deployed",
        "military alliance formed",
    ],

    "SIG_ALLIANCE_SHIFT": [
        "alliance realignment",
        "defense deal signed",
        "strategic partnership",
        "arms deal approved",
    ],

    "SIG_DECEPTION_ACTIVITY": [
        "disinformation campaign",
        "propaganda operations",
        "false flag operation",
        "information warfare",
    ],

    "SIG_RETALIATORY_THREAT": [
        "retaliation threat",
        "counter strike warning",
        "revenge attack",
        "response threatened",
    ],

    "SIG_DETERRENCE_SIGNALING": [
        "show of force",
        "deterrence maneuver",
        "military warning",
        "strategic signaling",
    ],
}


# =====================================================================
# Module-level search result cache (avoid hammering search engines)
# =====================================================================
_search_cache: Dict[str, List[Dict[str, str]]] = {}
_search_cache_ts: float = 0.0
_SEARCH_CACHE_TTL = 300.0  # 5 minutes

# ── Article text cache (avoid re-fetching same URL) ────────────
_article_cache: Dict[str, Any] = {}
_MAX_ARTICLE_CACHE = 100

# ── Rate limiting ──────────────────────────────────────────────
_last_search_time: float = 0.0
_SEARCH_DELAY = 1.5  # seconds between search requests
_last_fetch_time: float = 0.0
_FETCH_DELAY = 0.8   # seconds between article fetches

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
_REQUEST_TIMEOUT = 10  # seconds


# =====================================================================
# STEP 1: Signal → Search Queries
# =====================================================================

def signal_to_queries(
    signal: str,
    country: str = "",
    max_queries: int = 3,
) -> List[str]:
    """
    Convert a signal code to concrete search queries.

    Parameters
    ----------
    signal : str
        Signal code (e.g. "SIG_FORCE_POSTURE").
    country : str
        Country name to scope the search.
    max_queries : int
        Maximum number of queries to generate.

    Returns
    -------
    list[str]
        Search query strings like ["Iran troop deployment", "Iran military exercise"].
    """
    templates = SIGNAL_QUERY_MAP.get(signal.strip().upper(), [])
    if not templates:
        # Fallback: convert signal code to phrase
        phrase = signal.replace("SIG_", "").replace("_", " ").lower()
        templates = [phrase]

    queries = []
    for template in templates[:max_queries]:
        if country:
            queries.append(f"{country} {template}")
        else:
            queries.append(template)

    return queries


# =====================================================================
# STEP 2: Web Search (DuckDuckGo → Bing RSS → fallback)
# =====================================================================

def web_search(
    query: str,
    max_results: int = 5,
) -> List[Dict[str, str]]:
    """
    Search the web for a query string.

    Tries DuckDuckGo HTML first, then Bing RSS, then Google News RSS.
    Returns list of {title, url, snippet} dicts.

    No API keys needed — all public endpoints.
    """
    import requests as req
    global _search_cache, _search_cache_ts, _last_search_time

    # Check cache
    cache_key = query.lower().strip()
    now = time.time()
    if cache_key in _search_cache and (now - _search_cache_ts) < _SEARCH_CACHE_TTL:
        return _search_cache[cache_key][:max_results]

    # Rate limit
    elapsed = now - _last_search_time
    if elapsed < _SEARCH_DELAY:
        time.sleep(_SEARCH_DELAY - elapsed)
    _last_search_time = time.time()

    results: List[Dict[str, str]] = []

    # ── Strategy 1: Bing News RSS (most reliable, no redirect issues) ──
    results = _search_bing_rss(query, max_results, req)
    if results:
        _search_cache[cache_key] = results
        _search_cache_ts = time.time()
        return results[:max_results]

    # ── Strategy 2: DuckDuckGo HTML ────────────────────────────
    results = _search_ddg(query, max_results, req)
    if results:
        _search_cache[cache_key] = results
        _search_cache_ts = time.time()
        return results[:max_results]

    # ── Strategy 3: Google News RSS ────────────────────────────
    results = _search_google_rss(query, max_results, req)
    if results:
        _search_cache[cache_key] = results
        _search_cache_ts = time.time()
        return results[:max_results]

    logger.info("[SEARCH] No results from any provider for: %s", query[:60])
    return []


def _search_ddg(
    query: str,
    max_results: int,
    req: Any,
) -> List[Dict[str, str]]:
    """Search DuckDuckGo HTML (no API key needed)."""
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        resp = req.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return []

        results = _parse_ddg_html(resp.text, max_results)
        if results:
            logger.info("[SEARCH:DDG] %d results for: %s", len(results), query[:50])
        return results

    except Exception as e:
        logger.debug("[SEARCH:DDG] Failed: %s", e)
        return []


def _parse_ddg_html(html: str, max_results: int) -> List[Dict[str, str]]:
    """Parse DuckDuckGo HTML search results."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
    except ImportError:
        soup = None
    except Exception:
        soup = None

    results: List[Dict[str, str]] = []

    if soup:
        # Strategy 1: Standard DDG CSS selectors
        for result_div in soup.select(".result, .web-result, .results_links"):
            if len(results) >= max_results:
                break

            link = (
                result_div.select_one(".result__a")
                or result_div.select_one("a.result-link")
                or result_div.select_one("a[href]")
            )
            snippet_el = (
                result_div.select_one(".result__snippet")
                or result_div.select_one(".result__body")
            )

            if not link:
                continue

            href = link.get("href", "")
            title = link.get_text(strip=True)
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            real_url = _extract_ddg_url(str(href))
            if not real_url or not title:
                continue

            results.append({
                "title": title,
                "url": real_url,
                "snippet": snippet,
            })

        # Strategy 2: If CSS selectors failed, find all <a> tags with uddg
        if not results:
            for a_tag in soup.find_all("a", href=True):
                if len(results) >= max_results:
                    break
                href = str(a_tag.get("href", ""))
                if "uddg=" in href:
                    real_url = _extract_ddg_url(href)
                    title = a_tag.get_text(strip=True)
                    if real_url and title and len(title) > 5:
                        results.append({"title": title, "url": real_url, "snippet": ""})
    else:
        # Regex fallback (no BeautifulSoup)
        pattern = r'href="([^"]*uddg=[^"]+)"[^>]*>([^<]+)</a>'
        for m in re.finditer(pattern, html):
            if len(results) >= max_results:
                break
            href, title = m.group(1), m.group(2).strip()
            real_url = _extract_ddg_url(href)
            if real_url and len(title) > 5:
                results.append({"title": title, "url": real_url, "snippet": ""})

    return results


def _extract_ddg_url(href: str) -> str:
    """Extract real URL from DuckDuckGo redirect wrapper."""
    if "uddg=" in href:
        # DDG format: /l/?uddg=https%3A%2F%2F...&rut=...
        from urllib.parse import parse_qs, urlparse as _urlparse
        parsed = _urlparse(href)
        params = parse_qs(parsed.query)
        uddg = params.get("uddg", [""])[0]
        if uddg:
            return uddg
    if href.startswith("http"):
        return href
    return ""


def _search_bing_rss(
    query: str,
    max_results: int,
    req: Any,
) -> List[Dict[str, str]]:
    """Search Bing News RSS (no API key needed)."""
    try:
        url = f"https://www.bing.com/news/search?q={quote_plus(query)}&format=RSS"
        resp = req.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return []

        return _parse_rss(resp.text, max_results, "BING")
    except Exception as e:
        logger.debug("[SEARCH:BING] Failed: %s", e)
        return []


def _search_google_rss(
    query: str,
    max_results: int,
    req: Any,
) -> List[Dict[str, str]]:
    """Search Google News RSS (no API key needed)."""
    try:
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en"
        resp = req.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return []

        return _parse_rss(resp.text, max_results, "GOOGLE")
    except Exception as e:
        logger.debug("[SEARCH:GOOGLE] Failed: %s", e)
        return []


def _parse_rss(xml_text: str, max_results: int, source: str) -> List[Dict[str, str]]:
    """Parse RSS/XML feed into search results."""
    results: List[Dict[str, str]] = []

    # Simple regex-based RSS parsing
    items = re.findall(r"<item>(.*?)</item>", xml_text, re.DOTALL)
    for item_xml in items[:max_results]:
        title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item_xml, re.DOTALL)
        link_m = re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", item_xml, re.DOTALL)
        desc_m = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", item_xml, re.DOTALL)

        title = title_m.group(1).strip() if title_m else ""
        link = link_m.group(1).strip() if link_m else ""
        desc = desc_m.group(1).strip() if desc_m else ""

        # For Bing RSS: extract REAL article URL (not the redirect)
        # Try <source url="..."> attribute first
        source_url_m = re.search(r'<source\s+url="([^"]+)"', item_xml)
        # Try <guid> element (often the actual URL)
        guid_m = re.search(r"<guid[^>]*>(?:<!\[CDATA\[)?(https?://[^<\]]+)(?:\]\]>)?</guid>", item_xml)
        # Try <NewsUrl> element (Bing-specific)
        newsurl_m = re.search(r"<news:Url>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</news:Url>", item_xml)

        # Pick the best URL (prefer non-redirect)
        real_url = ""
        for candidate_m in [source_url_m, guid_m, newsurl_m]:
            if candidate_m:
                candidate = candidate_m.group(1).strip()
                if candidate.startswith("http") and "bing.com" not in candidate:
                    real_url = candidate
                    break

        # If all URLs are Bing redirects, resolve the redirect
        if not real_url and link:
            real_url = _resolve_bing_redirect(link)

        # Fallback: use link as-is
        if not real_url:
            real_url = link

        # Unescape HTML entities in URL
        real_url = real_url.replace("&amp;", "&")

        # Clean HTML from description
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = re.sub(r"\s+", " ", desc).strip()

        if real_url and title:
            results.append({
                "title": title,
                "url": real_url,
                "snippet": desc[:300],
            })

    if results:
        logger.info("[SEARCH:%s] %d results from RSS", source, len(results))
    return results


def _resolve_bing_redirect(bing_url: str) -> str:
    """Resolve a Bing redirect URL to the actual article URL."""
    import requests as req
    try:
        # Unescape HTML entities first
        clean_url = bing_url.replace("&amp;", "&")
        resp = req.head(
            clean_url,
            headers={"User-Agent": _USER_AGENT},
            timeout=5,
            allow_redirects=True,
        )
        final_url = resp.url
        if final_url and "bing.com" not in final_url:
            return final_url
    except Exception:
        pass
    return bing_url.replace("&amp;", "&")


# =====================================================================
# STEP 3: Fetch Articles
# =====================================================================

def fetch_article(url: str) -> Tuple[str, str, str]:
    """
    Fetch and extract readable text + publish date from a URL.

    Uses BeautifulSoup to strip HTML tags and extract article body.
    Uses ``_extract_publish_date()`` to resolve event-time from HTML
    metadata, schema.org JSON-LD, URL path, and body-text heuristics.

    Returns
    -------
    (text, publish_date, date_strategy)
        text: clean article body (up to 10 000 chars), or ""
        publish_date: ISO "YYYY-MM-DD" or "" if not found
        date_strategy: extraction strategy tag ("og_meta", "schema_org",
            etc.) or "" if no date found
    """
    import requests as req
    global _article_cache, _last_fetch_time

    # Cache check — cache now stores (text, publish_date, strategy) tuples
    if url in _article_cache:
        cached = _article_cache[url]
        if isinstance(cached, tuple) and len(cached) == 3:
            return (str(cached[0]), str(cached[1]), str(cached[2]))
        if isinstance(cached, tuple) and len(cached) == 2:
            # Legacy 2-tuple — upgrade with empty strategy
            return (str(cached[0]), str(cached[1]), "")
        # Legacy str entry — return with empty date
        return (str(cached), "", "")

    # Rate limit
    now = time.time()
    elapsed = now - _last_fetch_time
    if elapsed < _FETCH_DELAY:
        time.sleep(_FETCH_DELAY - elapsed)
    _last_fetch_time = time.time()

    # Unescape HTML entities in URL
    url = url.replace("&amp;", "&")

    try:
        resp = req.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=_REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            logger.debug("[FETCH] HTTP %d for %s", resp.status_code, url[:60])
            return ("", "", "")

        # Limit content size (skip huge pages)
        content = resp.text[:500_000]

        # Extract publish date from raw HTML BEFORE stripping tags
        publish_date, date_strategy = _extract_publish_date(content, url)

        # Extract readable text
        text = _extract_article_text(content)

        # Cache it
        result = (text, publish_date, date_strategy)
        if len(_article_cache) >= _MAX_ARTICLE_CACHE:
            # Evict oldest entry
            oldest = next(iter(_article_cache))
            del _article_cache[oldest]
        _article_cache[url] = result

        if publish_date:
            logger.debug("[FETCH] %s → date=%s (strategy=%s)", url[:60], publish_date, date_strategy)

        return result

    except Exception as e:
        logger.debug("[FETCH] Failed for %s: %s", url[:60], e)
        return ("", "", "")


def _extract_article_text(html: str) -> str:
    """Extract readable text from HTML using BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
    except ImportError:
        # Fallback: strip HTML tags with regex
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:10_000]

    # Remove non-content elements
    for tag in soup.find_all(["script", "style", "nav", "header", "footer",
                              "aside", "iframe", "noscript", "form"]):
        tag.decompose()

    # Try to find article body
    article = (
        soup.find("article")
        or soup.find("div", class_=re.compile(r"article|story|content|body", re.I))
        or soup.find("main")
    )

    if article:
        text = article.get_text(separator=" ", strip=True)
    else:
        text = soup.get_text(separator=" ", strip=True)

    # Clean up
    text = re.sub(r"\s+", " ", text).strip()
    return text[:10_000]


# =====================================================================
# STEP 3b: Event Time Resolver  (extract real publish / event date)
# =====================================================================
# Intelligence recency MUST be based on *when the event occurred*,
# not when the article was scraped.  This function extracts the
# best-available date from HTML metadata and body text using a
# 6-strategy cascade (no LLM, pure heuristics).
# =====================================================================

# Month abbreviation map for body-text regex
_MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}

# Regex: ISO-like date anywhere
_RE_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
# Regex: "March 2, 2026" / "2 March 2026" / "Mar 02, 2026"
_RE_PROSE_DATE_MDY = re.compile(
    r"\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?))\s+(\d{1,2}),?\s+(\d{4})\b",
    re.IGNORECASE,
)
_RE_PROSE_DATE_DMY = re.compile(
    r"\b(\d{1,2})\s+((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?))\s+(\d{4})\b",
    re.IGNORECASE,
)
# Regex: URL-embedded date  /2026/03/02/ or /20260302/
_RE_URL_DATE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")
_RE_URL_DATE_COMPACT = re.compile(r"/(\d{4})(\d{2})(\d{2})/")
# Schema.org JSON-LD datePublished
_RE_SCHEMA_DATE = re.compile(
    r'"datePublished"\s*:\s*"([^"]{8,25})"', re.IGNORECASE,
)


def _validate_date_parts(year: str, month: str, day: str) -> str:
    """Return ISO date string if parts are valid, else ''."""
    try:
        y, m, d = int(year), int(month), int(day)
        if not (1990 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31):
            return ""
        return f"{y:04d}-{m:02d}-{d:02d}"
    except (ValueError, TypeError):
        return ""


# ── Date confidence by extraction strategy ────────────────────────
# Higher confidence = more trustworthy temporal signal.
# OG / schema.org are author-supplied structured data.
# URL patterns are usually reliable for news sites.
# Prose-text is a last resort and often picks up irrelevant dates.
# crawl_time means we couldn't find ANY date — observation is temporally unanchored.
DATE_CONFIDENCE: Dict[str, float] = {
    "og_meta":      1.00,
    "meta_name":    0.90,
    "html5_time":   0.90,
    "schema_org":   1.00,
    "url_pattern":  0.70,
    "prose_text":   0.50,
    "crawl_time":   0.30,
}


def _extract_publish_date(html: str, url: str = "") -> Tuple[str, str]:
    """
    Extract the best-available publication / event date from HTML.

    Uses a 6-strategy cascade (first match wins):
        1. <meta property="article:published_time">  (Open Graph)
        2. <meta name="publish-date|date|pubdate">
        3. <time datetime="...">  (HTML5 semantic)
        4. Schema.org "datePublished" in JSON-LD
        5. Date embedded in URL path  (/2026/03/02/)
        6. Prose date in first 2000 chars of body text

    Returns
    -------
    tuple[str, str]
        (iso_date, strategy_tag) where strategy_tag is one of:
        "og_meta", "meta_name", "html5_time", "schema_org",
        "url_pattern", "prose_text", or "" if nothing found.
    """
    # ── Strategy 1: Open Graph meta ──────────────────────────────
    og_match = re.search(
        r'<meta\s[^>]*property\s*=\s*["\']article:published_time["\'][^>]*'
        r'content\s*=\s*["\']([^"\']+)["\']',
        html[:10_000], re.IGNORECASE,
    )
    if not og_match:
        og_match = re.search(
            r'<meta\s[^>]*content\s*=\s*["\']([^"\']+)["\'][^>]*'
            r'property\s*=\s*["\']article:published_time["\']',
            html[:10_000], re.IGNORECASE,
        )
    if og_match:
        iso = _RE_ISO_DATE.search(og_match.group(1))
        if iso:
            dt = _validate_date_parts(iso.group(1), iso.group(2), iso.group(3))
            if dt:
                logger.debug("[EVENT-TIME] Strategy 1 (OG meta): %s", dt)
                return (dt, "og_meta")

    # ── Strategy 2: generic <meta name="date|publish-date|pubdate"> ─
    for name_attr in ("date", "publish-date", "pubdate", "article_date_original",
                       "sailthru.date", "DC.date.issued", "parsely-pub-date"):
        meta_match = re.search(
            rf'<meta\s[^>]*name\s*=\s*["\'](?i:{re.escape(name_attr)})["\'][^>]*'
            r'content\s*=\s*["\']([^"\']+)["\']',
            html[:10_000], re.IGNORECASE,
        )
        if not meta_match:
            meta_match = re.search(
                r'<meta\s[^>]*content\s*=\s*["\']([^"\']+)["\'][^>]*'
                rf'name\s*=\s*["\'](?i:{re.escape(name_attr)})["\']',
                html[:10_000], re.IGNORECASE,
            )
        if meta_match:
            iso = _RE_ISO_DATE.search(meta_match.group(1))
            if iso:
                dt = _validate_date_parts(iso.group(1), iso.group(2), iso.group(3))
                if dt:
                    logger.debug("[EVENT-TIME] Strategy 2 (meta name=%s): %s", name_attr, dt)
                    return (dt, "meta_name")

    # ── Strategy 3: <time datetime="..."> ────────────────────────
    time_match = re.search(
        r'<time[^>]*datetime\s*=\s*["\']([^"\']+)["\']',
        html[:20_000], re.IGNORECASE,
    )
    if time_match:
        iso = _RE_ISO_DATE.search(time_match.group(1))
        if iso:
            dt = _validate_date_parts(iso.group(1), iso.group(2), iso.group(3))
            if dt:
                logger.debug("[EVENT-TIME] Strategy 3 (<time>): %s", dt)
                return (dt, "html5_time")

    # ── Strategy 4: Schema.org JSON-LD datePublished ─────────────
    schema_match = _RE_SCHEMA_DATE.search(html[:30_000])
    if schema_match:
        iso = _RE_ISO_DATE.search(schema_match.group(1))
        if iso:
            dt = _validate_date_parts(iso.group(1), iso.group(2), iso.group(3))
            if dt:
                logger.debug("[EVENT-TIME] Strategy 4 (schema.org): %s", dt)
                return (dt, "schema_org")

    # ── Strategy 5: Date in URL ──────────────────────────────────
    if url:
        url_m = _RE_URL_DATE.search(url)
        if not url_m:
            url_m = _RE_URL_DATE_COMPACT.search(url)
        if url_m:
            dt = _validate_date_parts(url_m.group(1), url_m.group(2), url_m.group(3))
            if dt:
                logger.debug("[EVENT-TIME] Strategy 5 (URL): %s from %s", dt, url[:60])
                return (dt, "url_pattern")

    # ── Strategy 6: Prose date in body text (first 2000 chars) ───
    body_head = html[:2000]
    # Try "Month DD, YYYY" first
    prose_m = _RE_PROSE_DATE_MDY.search(body_head)
    if prose_m:
        month_key = prose_m.group(1).lower()[:3]
        m_num = _MONTH_MAP.get(month_key, "")
        if m_num:
            dt = _validate_date_parts(prose_m.group(3), m_num, prose_m.group(2))
            if dt:
                logger.debug("[EVENT-TIME] Strategy 6a (prose MDY): %s", dt)
                return (dt, "prose_text")
    # Try "DD Month YYYY"
    prose_m = _RE_PROSE_DATE_DMY.search(body_head)
    if prose_m:
        month_key = prose_m.group(2).lower()[:3]
        m_num = _MONTH_MAP.get(month_key, "")
        if m_num:
            dt = _validate_date_parts(prose_m.group(3), m_num, prose_m.group(1))
            if dt:
                logger.debug("[EVENT-TIME] Strategy 6b (prose DMY): %s", dt)
                return (dt, "prose_text")
    # Last resort: raw ISO date in text
    iso_m = _RE_ISO_DATE.search(body_head)
    if iso_m:
        dt = _validate_date_parts(iso_m.group(1), iso_m.group(2), iso_m.group(3))
        if dt:
            logger.debug("[EVENT-TIME] Strategy 6c (inline ISO): %s", dt)
            return (dt, "prose_text")

    logger.debug("[EVENT-TIME] No publish date found for %s", url[:60] if url else "(no url)")
    return ("", "")


# =====================================================================
# STEP 4: Full Sensor Pipeline  (signal → observations)
# =====================================================================

def sense_moltbot(
    signals: List[str],
    country: str = "",
    max_queries_per_signal: int = 2,
    max_articles_per_signal: int = 3,
    max_total_articles: int = 15,
) -> List[Dict[str, Any]]:
    """
    Full MoltBot sensor sweep — the main entry point.

    Mechanical pipeline (no LLM):
        1. Signals → search queries (mapping table)
        2. Search queries → URLs (DuckDuckGo / Bing RSS)
        3. URLs → article text (requests + BeautifulSoup)
        4. Article text → observations (regex pattern matching)

    Parameters
    ----------
    signals : list[str]
        Signal codes from curiosity controller / PIRs.
    country : str
        Country name to scope searches.
    max_queries_per_signal : int
        Max distinct search queries per signal.
    max_articles_per_signal : int
        Max articles to fetch per signal.
    max_total_articles : int
        Global article fetch budget.

    Returns
    -------
    list[dict]
        Observation dicts in the SAME format as GDELT sensor:
        {type, signal, source_type, evidence_strength, corroboration,
         keyword_hits, origin_id, source, url, timestamp, excerpt}
    """
    from engine.Layer1_Collection.moltbot_observation_extractor import extract_observations
    from engine.Layer1_Collection.sensors.relevance_filter import (
        score_relevance, RELEVANCE_THRESHOLD,
    )
    from engine.Layer1_Collection.sensors.event_classifier import extract_headline
    from Utils.country_normalization import (
        resolve_country_iso,
        resolve_country_name,
    )

    all_observations: List[Dict[str, Any]] = []
    total_articles_fetched = 0
    seen_urls: set = set()
    seen_origins: set = set()
    rejected_relevance = 0
    country_ref = str(country or "").strip()
    country_iso = resolve_country_iso(country_ref)
    country_name = resolve_country_name(country_ref)
    display_country = country_name or country_ref

    logger.info(
        "[MOLTBOT] Sensor sweep: %d signals, country=%s",
        len(signals), display_country or "(all)",
    )

    for signal in signals:
        signal = signal.strip().upper()
        if not signal:
            continue

        # 1. Signal → queries
        queries = signal_to_queries(signal, country_name, max_queries_per_signal)

        signal_articles = 0

        for query in queries:
            if total_articles_fetched >= max_total_articles:
                break
            if signal_articles >= max_articles_per_signal:
                break

            # 2. Search the web
            search_results = web_search(query, max_results=5)

            for sr in search_results:
                if total_articles_fetched >= max_total_articles:
                    break
                if signal_articles >= max_articles_per_signal:
                    break

                url = sr.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                # 3. Fetch article + extract publish date
                article_text, pub_date, date_strategy = fetch_article(url)
                if not article_text or len(article_text) < 50:
                    continue

                # 3b. Extract headline for relevance & eventness
                headline = extract_headline(article_text)

                # 3c. Relevance filter — reject wrong-country articles
                if country_ref:
                    relevance = score_relevance(
                        article_text,
                        country_iso or country_ref,
                        headline=headline,
                    )
                    if relevance < RELEVANCE_THRESHOLD:
                        logger.info(
                            "[RELEVANCE] Rejected: %s (score=%.2f, target=%s)",
                            url[:60], relevance, display_country or country_ref,
                        )
                        rejected_relevance += 1
                        continue

                total_articles_fetched += 1
                signal_articles += 1

                # 4. Extract observations (pattern matching)
                obs_list = extract_observations(
                    text=article_text,
                    url=url,
                    source_type="OSINT",
                    publish_date=pub_date,
                    date_strategy=date_strategy,
                    headline=headline,
                )

                for obs in obs_list:
                    origin = obs.get("origin_id", "")
                    if origin and origin in seen_origins:
                        continue
                    seen_origins.add(origin)
                    all_observations.append(obs)

        if signal_articles > 0:
            signal_obs = [o for o in all_observations if o.get("signal") == signal]
            logger.info(
                "[MOLTBOT] %s: %d articles → %d observations",
                signal, signal_articles, len(signal_obs),
            )

    logger.info(
        "[MOLTBOT] Sensor sweep complete: %d articles fetched → %d observations "
        "(%d rejected by relevance filter)",
        total_articles_fetched, len(all_observations), rejected_relevance,
    )

    return all_observations


# =====================================================================
# Convenience: collect_documents (backward-compatible with adapter)
# =====================================================================

def collect_documents(
    query: str = "",
    required_evidence: Optional[List[str]] = None,
    countries: Optional[List[str]] = None,
    missing_gaps: Optional[List[str]] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Backward-compatible document collection interface.

    This is called by moltbot_adapter._try_moltbot() and
    collection_bridge.execute_collection_plan().

    Converts the generic query into the structured sensor pipeline.
    """
    # Extract signal hints from required_evidence or missing_gaps
    signals = []
    for sig in (required_evidence or []) + (missing_gaps or []):
        sig = str(sig).strip().upper()
        if sig.startswith("SIG_"):
            signals.append(sig)

    # If no signals, try to infer from query keywords
    if not signals and query:
        signals = _infer_signals_from_query(query)

    # Country from countries list
    country = ""
    if countries:
        country = str(countries[0]).strip()

    if not signals:
        # Can't do structured search — return search results as raw docs
        results = web_search(query, max_results=limit)
        docs = []
        for r in results[:limit]:
            text, pub_date, date_strategy = fetch_article(r.get("url", ""))
            if text:
                _fallback_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                docs.append({
                    "content": text[:2000],
                    "text": text[:2000],
                    "url": r["url"],
                    "title": r.get("title", ""),
                    "date": pub_date or _fallback_date,
                    "date_source": date_strategy if pub_date else "crawl_time",
                    "source_url": r["url"],
                    "metadata": {"source": "MOLTBOT_WEB"},
                })
        return docs[:limit]

    # Structured sensor pipeline
    observations = sense_moltbot(
        signals=signals,
        country=country,
        max_total_articles=limit,
    )

    # Convert observations back to document format (for backward compat)
    docs = []
    for obs in observations:
        docs.append({
            "content": obs.get("excerpt", ""),
            "text": obs.get("excerpt", ""),
            "url": obs.get("url", ""),
            "title": f"[{obs.get('signal', '')}] OSINT Article",
            "date": obs.get("timestamp", ""),
            "source_url": obs.get("url", ""),
            "metadata": {"source": "MOLTBOT", "signal": obs.get("signal", "")},
            "raw_observation": obs,
        })

    return docs[:limit]


def _infer_signals_from_query(query: str) -> List[str]:
    """Infer likely signal codes from a free-text query."""
    query_lower = query.lower()
    inferred: List[str] = []

    _KEYWORD_SIGNAL: List[Tuple[str, str]] = [
        ("military", "SIG_MIL_ESCALATION"),
        ("troop", "SIG_FORCE_POSTURE"),
        ("missile", "SIG_MIL_ESCALATION"),
        ("cyber", "SIG_CYBER_ACTIVITY"),
        ("sanction", "SIG_ECON_PRESSURE"),
        ("nuclear", "SIG_WMD_RISK"),
        ("protest", "SIG_INTERNAL_INSTABILITY"),
        ("diplomat", "SIG_DIP_HOSTILITY"),
        ("negotiation", "SIG_NEGOTIATION_BREAKDOWN"),
        ("alliance", "SIG_ALLIANCE_ACTIVATION"),
    ]

    for keyword, signal in _KEYWORD_SIGNAL:
        if keyword in query_lower and signal not in inferred:
            inferred.append(signal)

    return inferred


# =====================================================================
# Module-level agent-compatible singleton
# =====================================================================

class _MoltBotSensorAgent:
    """Agent facade — provides the interface moltbot_adapter expects."""

    def collect_documents(self, **kwargs) -> List[Dict[str, Any]]:
        return collect_documents(**kwargs)

    def sense(self, signals: List[str], country: str = "", **kwargs) -> List[Dict[str, Any]]:
        return sense_moltbot(signals=signals, country=country, **kwargs)


moltbot_sensor = _MoltBotSensorAgent()


__all__ = [
    "SIGNAL_QUERY_MAP",
    "signal_to_queries",
    "web_search",
    "fetch_article",
    "sense_moltbot",
    "collect_documents",
    "moltbot_sensor",
]
