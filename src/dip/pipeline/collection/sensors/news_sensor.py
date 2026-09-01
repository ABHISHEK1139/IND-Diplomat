"""
News Sensor (OSINT)
===================
Uses DuckDuckGo News search as the primary source, with
Google News RSS as a fallback for real geopolitical news.
"""

import logging
import urllib.parse
from typing import List
from datetime import datetime, timezone
from dip.core.schema import RawObservation

logger = logging.getLogger("Layer1.news_sensor")

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False


class NewsSensor:
    def __init__(self):
        self.source_id = "NEWS_SENSOR"
        self.keywords = {
            "SIG_MIL_ESCALATION": ["troops", "military", "deploy", "attack", "missile", "war"],
            "SIG_ECONOMIC_PRESSURE": ["sanction", "tariff", "trade war", "embargo"],
            "SIG_DIPLOMACY_ACTIVE": ["diplomat", "treaty", "negotiate", "summit", "visit"],
            "SIG_DIP_HOSTILITY": ["condemn", "expel", "threaten", "warn"],
        }

    def _classify_signal(self, text: str) -> str | None:
        """Match text against known signal keywords and return CAMEO code."""
        content = text.lower()
        for sig, words in self.keywords.items():
            if any(w in content for w in words):
                if sig == "SIG_MIL_ESCALATION":
                    return "18"
                elif sig == "SIG_ECONOMIC_PRESSURE":
                    return "16"
                elif sig == "SIG_DIPLOMACY_ACTIVE":
                    return "04"
                elif sig == "SIG_DIP_HOSTILITY":
                    return "11"
        return None

    async def fetch(self, country: str = "IND") -> List[RawObservation]:
        """Fetch news using DuckDuckGo (primary) with Google RSS fallback."""
        # Primary: DuckDuckGo News
        observations = await self._fetch_ddg(country)

        # Fallback: Google News RSS if DDG returned nothing
        if not observations:
            observations = await self._fetch_google_rss(country)

        return observations

    async def _fetch_ddg(self, country: str) -> List[RawObservation]:
        """Fetch news using ResilientWebSurfer with multi-provider fallback."""
        from dip.pipeline.collection.research.retrieval.web_surfer import web_surfer
        query = f"{country} geopolitics military economy diplomacy"
        try:
            raw_obs = await web_surfer.search(query, country_code=country, max_results=15)
            observations = []
            for obs in raw_obs:
                matched_cameo = self._classify_signal(obs.content)
                observations.append(RawObservation(
                    source_id="RESILIENT_NEWS_SURFER",
                    source_type="NEWS",
                    content=obs.content,
                    timestamp=obs.timestamp or datetime.now(timezone.utc).isoformat(),
                    country=country,
                    cameo_code=matched_cameo,
                ))
            return observations
        except Exception as e:
            logger.warning(f"Resilient Web Surfer fetch encountered error: {e}")
            return []

    async def _fetch_google_rss(self, country: str) -> List[RawObservation]:
        """Fallback: Fetch news from Google News RSS."""
        if not FEEDPARSER_AVAILABLE:
            return []

        observations = []
        try:
            query = urllib.parse.quote(f"{country} geopolitics OR military OR economy")
            rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

            feed = feedparser.parse(rss_url)
            results = feed.entries[:15]

            for res in results:
                title = res.get("title", "")
                link = res.get("link", "")
                pub_date = res.get("published", datetime.now(timezone.utc).isoformat())

                matched_cameo = self._classify_signal(title)

                observations.append(RawObservation(
                    source_id="GOOGLE_NEWS_RSS",
                    source_type="NEWS",
                    content=f"{title} - {link}",
                    timestamp=pub_date,
                    country=country,
                    cameo_code=matched_cameo,
                ))

            logger.info(f"Google RSS: fetched {len(observations)} news signals for {country}")

        except Exception as e:
            logger.error(f"Google News RSS fetch failed: {e}")

        return observations
