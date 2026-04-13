"""
Lightweight OSINT RSS sensor.

This sensor is intentionally simple and returns normalized article stubs.
"""

from __future__ import annotations

from typing import Any, Dict, List
from xml.etree import ElementTree as ET
from urllib.parse import quote_plus

import requests


def search_news(query: str, timeout: int = 12) -> List[Dict[str, Any]]:
    token = str(query or "").strip()
    if not token:
        return []

    url = f"https://news.google.com/rss/search?q={quote_plus(token)}&hl=en-US&gl=US&ceid=US:en"
    response = requests.get(url, timeout=max(3, int(timeout or 12)))
    response.raise_for_status()

    root = ET.fromstring(response.text)
    items: List[Dict[str, Any]] = []
    for node in root.findall(".//item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        pub_date = (node.findtext("pubDate") or "").strip()
        description = (node.findtext("description") or "").strip()
        if not title and not description:
            continue
        items.append(
            {
                "id": link or title,
                "source": "GoogleNewsRSS",
                "url": link,
                "publication_date": pub_date,
                "content": f"{title}. {description}".strip(),
                "score": 0.6,
                "metadata": {
                    "source": "GoogleNewsRSS",
                    "type": "news",
                    "url": link,
                    "publication_date": pub_date,
                },
            }
        )
    return items


__all__ = ["search_news"]

