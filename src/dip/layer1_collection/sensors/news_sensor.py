"""
News Sensor (OSINT)
===================
Uses Google News RSS to search for real geopolitical news.
"""

import logging
import feedparser
import urllib.parse
from typing import List
from datetime import datetime, timezone
from dip.core.schema import RawObservation

logger = logging.getLogger("Layer1.news_sensor")

class NewsSensor:
    def __init__(self):
        self.source_id = "GOOGLE_NEWS_RSS"
        self.keywords = {
            "SIG_MIL_ESCALATION": ["troops", "military", "deploy", "attack", "missile", "war"],
            "SIG_ECONOMIC_PRESSURE": ["sanction", "tariff", "trade war", "embargo"],
            "SIG_DIPLOMACY_ACTIVE": ["diplomat", "treaty", "negotiate", "summit", "visit"],
            "SIG_DIP_HOSTILITY": ["condemn", "expel", "threaten", "warn"]
        }

    async def fetch(self, country: str = "IND") -> List[RawObservation]:
        observations = []
        try:
            # URL encode the country name for the query
            query = urllib.parse.quote(f"{country} geopolitics OR military OR economy")
            rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            
            feed = feedparser.parse(rss_url)
            
            # Take top 15 results
            results = feed.entries[:15]
            
            for res in results:
                title = res.get("title", "")
                link = res.get("link", "")
                pub_date = res.get("published", datetime.now(timezone.utc).isoformat())
                
                content = f"{title}".lower()
                
                matched_cameo = None
                for sig, words in self.keywords.items():
                    if any(w in content for w in words):
                        if sig == "SIG_MIL_ESCALATION": matched_cameo = "18"
                        elif sig == "SIG_ECONOMIC_PRESSURE": matched_cameo = "16"
                        elif sig == "SIG_DIPLOMACY_ACTIVE": matched_cameo = "04"
                        elif sig == "SIG_DIP_HOSTILITY": matched_cameo = "11"
                        break
                
                observations.append(RawObservation(
                    source_id=self.source_id,
                    source_type="NEWS",
                    content=f"{title} - {link}",
                    timestamp=pub_date,
                    country=country,
                    cameo_code=matched_cameo,
                ))
            
            logger.info(f"Successfully fetched {len(observations)} live news signals for {country}")
            
        except Exception as e:
            logger.error(f"Google News RSS fetch failed: {e}")
        
        return observations
