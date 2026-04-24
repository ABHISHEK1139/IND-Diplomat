"""Validate internet retrieval stack for MolTBolt style collection."""

from __future__ import annotations

import json
import sys
from typing import List

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS


def fail(reason: str) -> int:
    print(f"INTERNET_SEARCH_FAILED: {reason}")
    return 1


def main() -> int:
    query = "China Taiwan tensions news"
    try:
        results = list(DDGS().text(query, max_results=8))
    except Exception as exc:
        return fail(f"ddgs search error: {exc}")

    links: List[str] = []
    for row in results:
        url = str(row.get("href") or row.get("url") or "").strip()
        if url.startswith("http"):
            links.append(url)
    unique_links = list(dict.fromkeys(links))
    if len(unique_links) < 3:
        return fail(f"Expected >= 3 links, got {len(unique_links)}")

    target = unique_links[0]
    try:
        response = requests.get(target, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    except Exception as exc:
        return fail(f"requests GET failed for {target}: {exc}")
    if response.status_code >= 400:
        return fail(f"HTTP status {response.status_code} for {target}")

    try:
        soup = BeautifulSoup(response.text, "lxml")
        title = (soup.title.string or "").strip() if soup.title else ""
    except Exception as exc:
        return fail(f"BeautifulSoup parse failed: {exc}")

    print(
        json.dumps(
            {
                "query": query,
                "link_count": len(unique_links),
                "sample_link": target,
                "sample_title": title,
            },
            indent=2,
        )
    )
    print("INTERNET_SEARCH_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
