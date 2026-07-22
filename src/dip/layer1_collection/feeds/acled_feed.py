from __future__ import annotations
from dip.Config.config import config
"""
ACLED Feed Adapter — Armed Conflict Location & Event Data
==========================================================

Fetches ACLED conflict data for a given country/region.
ACLED provides real-time data on political violence and protest events.

API: https://api.acleddata.com/acled/read
"""


import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Layer1_Collection.acled_feed")


class ACLEDFeed:
    """ACLED data feed adapter."""

    def __init__(self, api_key: Optional[str] = None, email: Optional[str] = None):
        self.api_key = api_key or config.ACLED_API_KEY
        self.email = email or config.ACLED_EMAIL
        self.base_url = "https://api.acleddata.com/acled/read"

    async def fetch_events(
        self,
        country: str = "IND",
        days_back: int = 7,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Fetch recent conflict events for a country."""
        import urllib.request
        import json as _json

        if not self.api_key or not self.email:
            logger.warning("ACLED credentials not configured")
            return []

        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

        url = (
            f"{self.base_url}?key={self.api_key}&email={self.email}"
            f"&country={country}&event_date={start_date}|{end_date}"
            f"&event_date_where=BETWEEN&limit={limit}"
        )

        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = _json.loads(resp.read().decode())
                if data.get("status") == 200:
                    return data.get("data", [])
                logger.warning("ACLED API error: %s", data.get("error", {}).get("message", "unknown"))
                return []
        except Exception as e:
            logger.debug("ACLED fetch failed: %s", e)
            return []
