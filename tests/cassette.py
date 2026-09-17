"""Offline collection cassettes: deterministic sensor fixtures.

Activated via the ``DIP_OFFLINE=1`` environment switch (see conftest.py).
Every network-touching collection hop is replaced with fixture data derived
from the requested query/country, so the full suite runs with no network
and no LLM:

  - GdeltSensor / NewsSensor / ResilientWebSurfer -> fixture observations
  - ACLED / OFAC feeds -> empty (no network)
  - FORCE_MINISTER_HEURISTIC=1 -> deterministic extraction + council

Cassettes return *realistic* multi-domain observations (not empty lists)
so pipeline logic — readiness, council, red team, CRAG, synthesis — still
executes against meaningful content.
"""
from __future__ import annotations

from datetime import datetime, timezone

from dip.core.schema import RawObservation


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def cassette_observations(query: str = "", country: str = "IND") -> list[RawObservation]:
    q = (query or "general assessment").strip()[:80]
    return [
        RawObservation(
            source_id="CASSETTE-GDELT",
            source_type="DATASET",
            content=f"GDELT cassette: heightened military posture reporting related to '{q}'",
            timestamp=_now(),
            country=country,
            cameo_code="18",
        ),
        RawObservation(
            source_id="CASSETTE-NEWS",
            source_type="NEWS",
            content=f"News cassette: diplomatic statements and troop movement coverage on '{q}'",
            timestamp=_now(),
            country=country,
            cameo_code="11",
        ),
        RawObservation(
            source_id="CASSETTE-OSINT",
            source_type="OSINT",
            content=f"OSINT cassette: trade and sanctions discussion touching '{q}'",
            timestamp=_now(),
            country=country,
            cameo_code="16",
        ),
    ]


def install_cassettes(monkeypatch) -> None:
    """Patch all network-touching collection hops. Idempotent per-test."""
    from dip.pipeline.collection.sensors.gdelt_sensor import GdeltSensor
    from dip.pipeline.collection.sensors.news_sensor import NewsSensor
    from dip.pipeline.collection.research.retrieval.web_surfer import ResilientWebSurfer
    from dip.pipeline.collection.feed_integrator import FeedIntegrator

    async def _fake_fetch(self, country: str = "IND"):
        return cassette_observations(country=country)

    async def _fake_search(self, query: str = "", country_code=None, max_results: int = 5):
        return cassette_observations(query=query, country=country_code or "IND")[:max_results]

    async def _fake_acled(self, country: str):
        return []

    async def _fake_ofac(self, country: str):
        return []

    monkeypatch.setattr(GdeltSensor, "fetch", _fake_fetch)
    monkeypatch.setattr(NewsSensor, "fetch", _fake_fetch)
    monkeypatch.setattr(ResilientWebSurfer, "search", _fake_search)
    monkeypatch.setattr(ResilientWebSurfer, "_search_ddgs_resilient", _fake_search)
    monkeypatch.setattr(FeedIntegrator, "_fetch_acled", _fake_acled)
    monkeypatch.setattr(FeedIntegrator, "_fetch_ofac", _fake_ofac)
