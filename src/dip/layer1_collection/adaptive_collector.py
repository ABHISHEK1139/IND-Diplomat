"""
Adaptive Collector — Deliberate Intelligence Collection
=========================================================

The NEW main entry point for Layer 1.

Instead of blindly fetching from every sensor, the Adaptive Collector:
    1. Reads the Investigation's CollectionPlan
    2. Selects the right sources from the Source Registry
    3. Generates targeted search queries
    4. Runs multi-round collection with budget constraints
    5. Deduplicates and validates all evidence
    6. Updates CollectionNeed statuses
    7. Logs everything to the investigation timeline

Flow:
    Investigation → Source Selection → Query Generation → Collection Rounds
    → Deduplication → Validation → Persisted Evidence
"""

import asyncio
import logging
import time
import urllib.parse
from datetime import datetime, timezone
from typing import List, Dict, Optional

from dip.core.schema import Investigation, RawObservation, TimelineEvent
from dip.core.investigation_store import InvestigationStore
from dip.layer1_collection.source_registry import SourceRegistry, SourceEntry
from dip.layer1_collection.source_selector import SourceSelector
from dip.layer1_collection.query_generator import QueryGenerator
from dip.layer1_collection.deduplicator import Deduplicator
from dip.layer1_collection.validator import SourceValidator
from dip.layer1_collection.budget_manager import BudgetManager
from dip.layer1_collection.stopping_criteria import StoppingCriteria
from dip.layer1_collection.missing_evidence import MissingEvidenceDetector
from dip.layer1_collection.sensors.gdelt_sensor import GdeltSensor
from dip.layer1_collection.sensors.news_sensor import NewsSensor

logger = logging.getLogger("Layer1.AdaptiveCollector")


class AdaptiveCollector:
    """
    Deliberate, investigation-driven intelligence collection.

    Replaces the old FeedIntegrator's indiscriminate approach with
    targeted, multi-round collection guided by the CollectionPlan.
    """

    def __init__(self, store: InvestigationStore = None):
        self.store = store or InvestigationStore()
        self.selector = SourceSelector()
        self.query_gen = QueryGenerator()
        self.deduplicator = Deduplicator()
        self.validator = SourceValidator()
        self.missing_evidence = MissingEvidenceDetector()

        # Sensor instances (the ones we actually have implemented)
        self._sensors = {
            "gdelt": GdeltSensor(),
            "google_news": NewsSensor(),
        }
        # Lazy-init for optional sensors
        self._optional_sensors_loaded = False

    def _load_optional_sensors(self):
        """Try to load ACLED, OFAC sensors if available."""
        if self._optional_sensors_loaded:
            return
        try:
            from dip.layer1_collection.feeds.acled_feed import ACLEDFeed
            self._sensors["acled"] = ACLEDFeed()
        except (ImportError, Exception):
            pass
        try:
            from dip.layer1_collection.feeds.ofac_sipri_feed import OFACFeed
            self._sensors["ofac_sipri"] = OFACFeed()
        except (ImportError, Exception):
            pass
        self._optional_sensors_loaded = True

    async def collect(self, investigation: Investigation) -> List[RawObservation]:
        """
        Main collection method. Multi-round, budget-aware, investigation-driven.

        Returns validated, deduplicated observations.
        """
        start_time = time.time()
        self._load_optional_sensors()

        # 1. Select sources
        selected_sources = self.selector.select(investigation)
        available_sources = [s for s in selected_sources if s.source_id in self._sensors]
        unavailable_sources = [s for s in selected_sources if s.source_id not in self._sensors]

        logger.info(f"Available sensors: {[s.source_id for s in available_sources]}")
        if unavailable_sources:
            logger.info(f"Unavailable (no sensor): {[s.source_id for s in unavailable_sources]}")

        # 2. Generate queries
        queries = self.query_gen.generate(investigation)

        # 3. Multi-round collection
        budget = BudgetManager(max_articles=200, max_time_seconds=300)
        stopper = StoppingCriteria(min_observations=15, max_rounds=2)
        all_observations: List[RawObservation] = []
        round_num = 0

        while not stopper.should_stop(len(all_observations), round_num, not budget.can_collect()):
            round_num += 1
            logger.info(f"--- Collection Round {round_num} ---")

            round_obs = await self._collect_round(investigation, available_sources, queries, round_num)
            budget.record_collection(len(round_obs))
            all_observations.extend(round_obs)

            logger.info(f"Round {round_num}: {len(round_obs)} new observations | Total: {len(all_observations)} | {budget.summary()}")
            
            # Detect missing evidence to steer the next round
            if not stopper.should_stop(len(all_observations), round_num, not budget.can_collect()):
                new_queries = self.missing_evidence.detect(investigation, all_observations)
                if new_queries:
                    if "News" not in queries:
                        queries["News"] = []
                    queries["News"].extend(new_queries)

        logger.info(f"Collection stopped: {stopper.reason}")

        # 4. Deduplicate
        unique_obs = self.deduplicator.deduplicate(all_observations)

        # 5. Validate
        validated = self.validator.validate_batch(unique_obs)
        final_obs = [v.observation for v in validated]

        # 6. Update CollectionNeed statuses
        self._update_collection_status(investigation, available_sources, unavailable_sources)

        # 7. Log to timeline
        elapsed = time.time() - start_time
        self.store.append_timeline(
            investigation.investigation_id,
            TimelineEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type="COLLECTION_COMPLETE",
                description=(
                    f"Collected {len(all_observations)} raw → {len(unique_obs)} unique → "
                    f"{len(final_obs)} validated in {round_num} rounds ({elapsed:.1f}s)"
                ),
                layer="Layer1",
                metadata={
                    "rounds": round_num,
                    "raw_count": len(all_observations),
                    "unique_count": len(unique_obs),
                    "validated_count": len(final_obs),
                    "sources_used": [s.source_id for s in available_sources],
                    "sources_unavailable": [s.source_id for s in unavailable_sources],
                    "stop_reason": stopper.reason,
                    "elapsed_seconds": round(elapsed, 1),
                },
            ),
        )

        logger.info(
            f"Collection complete: {len(all_observations)} raw → {len(unique_obs)} unique → "
            f"{len(final_obs)} validated observations"
        )
        return final_obs

    async def _collect_round(
        self,
        investigation: Investigation,
        sources: List[SourceEntry],
        queries: Dict[str, List[str]],
        round_num: int,
    ) -> List[RawObservation]:
        """Execute a single collection round across available sensors."""
        tasks = []

        country = investigation.scope.countries[0] if investigation.scope.countries else "Global"

        for source in sources:
            sensor = self._sensors.get(source.source_id)
            if not sensor:
                continue

            if source.source_id == "gdelt":
                tasks.append(self._fetch_gdelt(sensor, country))
            elif source.source_id == "google_news":
                # Use generated queries for news
                news_queries = queries.get("News", [investigation.title])
                tasks.append(self._fetch_news(sensor, news_queries, country))
            elif source.source_id == "acled":
                tasks.append(self._fetch_generic(sensor, country))
            elif source.source_id == "ofac_sipri":
                tasks.append(self._fetch_generic(sensor, country))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        observations = []
        for res in results:
            if isinstance(res, list):
                observations.extend(res)
            elif isinstance(res, Exception):
                logger.debug(f"Sensor error in round {round_num}: {res}")

        return observations

    async def _fetch_gdelt(self, sensor: GdeltSensor, country: str) -> List[RawObservation]:
        """Fetch from GDELT sensor."""
        try:
            return await sensor.fetch(country)
        except Exception as e:
            logger.debug(f"GDELT fetch failed: {e}")
            return []

    async def _fetch_news(self, sensor: NewsSensor, queries: List[str], country: str) -> List[RawObservation]:
        """Fetch news using multiple targeted queries instead of just country name."""
        all_obs = []
        # Use up to 5 queries to avoid rate limiting
        for query in queries[:5]:
            try:
                import feedparser
                encoded_query = urllib.parse.quote(query)
                rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
                feed = feedparser.parse(rss_url)

                for entry in feed.entries[:5]:  # 5 per query
                    all_obs.append(RawObservation(
                        source_id="GOOGLE_NEWS_RSS",
                        source_type="NEWS",
                        content=f"{entry.get('title', '')} - {entry.get('link', '')}",
                        timestamp=entry.get("published", datetime.now(timezone.utc).isoformat()),
                        country=country,
                    ))
            except Exception as e:
                logger.debug(f"News query '{query}' failed: {e}")

        return all_obs

    async def _fetch_generic(self, sensor, country: str) -> List[RawObservation]:
        """Generic fetch for sensors with a .fetch(country) interface."""
        try:
            return await sensor.fetch(country)
        except Exception as e:
            logger.debug(f"Generic sensor fetch failed: {e}")
            return []

    def _update_collection_status(
        self,
        investigation: Investigation,
        available: List[SourceEntry],
        unavailable: List[SourceEntry],
    ) -> None:
        """Mark CollectionNeeds as Collected or Skipped based on what ran."""
        available_categories = {s.category.lower() for s in available}
        available_domains = set()
        for s in available:
            available_domains.update(d.lower() for d in s.domains)

        for need in investigation.collection_plan.needs:
            need_key = need.source_type.lower()
            if need_key in available_categories or any(d in need_key for d in available_domains):
                need.status = "Collected"
            else:
                need.status = "Skipped"
