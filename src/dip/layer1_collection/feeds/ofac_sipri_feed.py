from __future__ import annotations

"""OFAC Sanctions Feed — Office of Foreign Assets Control sanctions data."""

import csv
import io
import logging
import os
import urllib.request
from typing import Any, Dict, List

logger = logging.getLogger("Layer1_Collection.ofac_feed")

OFAC_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"


class OFACFeed:
    """OFAC SDN (Specially Designated Nationals) list adapter."""

    async def fetch_entries(self, country_hint: str = "") -> List[Dict[str, Any]]:
        """Fetch OFAC sanctions entries, optionally filtered by country."""
        try:
            req = urllib.request.Request(OFAC_URL, headers={"User-Agent": "DIP2/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            logger.debug("OFAC fetch failed: %s", e)
            return []

        entries = []
        reader = csv.DictReader(io.StringIO(raw))
        for row in reader:
            if country_hint and country_hint.upper() not in str(row.get("country", "")).upper():
                continue
            entries.append({
                "name": row.get("SDN_Name", ""),
                "type": row.get("SDN_Type", ""),
                "program": row.get("Program", ""),
                "country": row.get("country", ""),
            })
        return entries[:100]


class SIPRIFeed:
    """SIPRI Arms Transfer data adapter."""

    async def fetch_transfers(self, country: str = "IND") -> List[Dict[str, Any]]:
        """Fetch SIPRI arms transfer data (requires local database)."""
        # SIPRI data is typically distributed as CSV/excel, not API
        # Placeholder for local file loading
        logger.info("SIPRI feed: use local SIPRI database or CSV import")
        return []
