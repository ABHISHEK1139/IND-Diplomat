"""
Source Registry — Catalog of All Available Data Sources
========================================================

Every source in the intelligence ecosystem is registered here with
its reliability, cost, domains, and whether DIP has a working sensor for it.
"""

import logging
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

logger = logging.getLogger("Layer1.SourceRegistry")


class SourceEntry(BaseModel):
    """A registered data source in the DIP collection ecosystem."""
    source_id: str
    name: str
    category: str                     # News, Economic, Technology, Military, Government, Research, Climate, Health, Legal
    reliability: float                # 0.0 - 1.0
    update_frequency: str             # Real-time, Hourly, Daily, Weekly, Monthly
    cost: str = "Free"                # Free, Low, Medium, High
    latency: str = "Fast"             # Fast, Medium, Slow
    requires_auth: bool = False
    domains: List[str] = Field(default_factory=list)
    sensor_class: Optional[str] = None  # Python class path if we have a working sensor


# Cost ranking for sorting
_COST_RANK = {"Free": 0, "Low": 1, "Medium": 2, "High": 3}


class SourceRegistry:
    """
    Catalog of all available data sources.

    Each source declares what domains it covers, its reliability score,
    and whether DIP has a live sensor implementation for it.
    """

    def __init__(self):
        self._sources: Dict[str, SourceEntry] = {}
        self._populate()

    def _populate(self):
        """Register all known sources."""
        entries = [
            # --- News ---
            SourceEntry(source_id="gdelt", name="GDELT Project", category="News",
                        reliability=0.75, update_frequency="Real-time", cost="Free",
                        domains=["Military", "Geopolitics", "Diplomacy", "Conflict", "Security"],
                        sensor_class="layer1_collection.sensors.gdelt_sensor.GdeltSensor"),
            SourceEntry(source_id="google_news", name="Google News RSS", category="News",
                        reliability=0.65, update_frequency="Real-time", cost="Free",
                        domains=["General", "Economy", "Technology", "Military", "Politics", "AI", "Health", "Climate"],
                        sensor_class="layer1_collection.sensors.news_sensor.NewsSensor"),
            SourceEntry(source_id="reuters_rss", name="Reuters RSS", category="News",
                        reliability=0.92, update_frequency="Hourly", cost="Free",
                        domains=["General", "Economy", "Politics", "Diplomacy", "Trade"]),
            SourceEntry(source_id="bbc_rss", name="BBC News RSS", category="News",
                        reliability=0.88, update_frequency="Hourly", cost="Free",
                        domains=["General", "Politics", "Economy", "Health", "Climate"]),
            SourceEntry(source_id="ap_rss", name="Associated Press RSS", category="News",
                        reliability=0.90, update_frequency="Hourly", cost="Free",
                        domains=["General", "Politics", "Diplomacy", "Military"]),

            # --- Military / Conflict ---
            SourceEntry(source_id="acled", name="ACLED Conflict Data", category="Military",
                        reliability=0.93, update_frequency="Weekly", cost="Free", requires_auth=True,
                        domains=["Military", "Conflict", "Security", "Geopolitics"],
                        sensor_class="layer1_collection.feeds.acled_feed.ACLEDFeed"),
            SourceEntry(source_id="ofac_sipri", name="OFAC/SIPRI Sanctions & Arms", category="Military",
                        reliability=0.95, update_frequency="Monthly", cost="Free",
                        domains=["Military", "Sanctions", "Trade", "Security"],
                        sensor_class="layer1_collection.feeds.ofac_sipri_feed.OFACFeed"),

            # --- Economic ---
            SourceEntry(source_id="imf", name="IMF Data API", category="Economic",
                        reliability=0.96, update_frequency="Monthly", cost="Free",
                        domains=["Economy", "Finance", "Trade", "Debt", "Inflation"]),
            SourceEntry(source_id="worldbank", name="World Bank Open Data", category="Economic",
                        reliability=0.95, update_frequency="Monthly", cost="Free",
                        domains=["Economy", "Development", "Poverty", "Education", "Health", "Infrastructure"]),
            SourceEntry(source_id="oecd", name="OECD Data", category="Economic",
                        reliability=0.94, update_frequency="Monthly", cost="Free",
                        domains=["Economy", "Trade", "Education", "Innovation", "Tax"]),
            SourceEntry(source_id="trading_economics", name="Trading Economics", category="Economic",
                        reliability=0.85, update_frequency="Daily", cost="Medium", requires_auth=True,
                        domains=["Economy", "Finance", "Inflation", "GDP", "Trade"]),

            # --- Technology / Research ---
            SourceEntry(source_id="arxiv", name="arXiv Preprints", category="Research",
                        reliability=0.80, update_frequency="Daily", cost="Free",
                        domains=["AI", "Technology", "Science", "Research", "Mathematics", "Physics"]),
            SourceEntry(source_id="semantic_scholar", name="Semantic Scholar", category="Research",
                        reliability=0.85, update_frequency="Daily", cost="Free",
                        domains=["AI", "Technology", "Science", "Research", "Medicine"]),
            SourceEntry(source_id="openalex", name="OpenAlex", category="Research",
                        reliability=0.82, update_frequency="Daily", cost="Free",
                        domains=["Research", "Science", "Education", "AI", "Technology"]),
            SourceEntry(source_id="pubmed", name="PubMed / NCBI", category="Research",
                        reliability=0.93, update_frequency="Daily", cost="Free",
                        domains=["Health", "Medicine", "Biotech", "Research"]),
            SourceEntry(source_id="github", name="GitHub Trending", category="Technology",
                        reliability=0.60, update_frequency="Real-time", cost="Free",
                        domains=["AI", "Technology", "Software", "Open Source"]),
            SourceEntry(source_id="patents", name="Patent Databases (WIPO/USPTO)", category="Technology",
                        reliability=0.95, update_frequency="Weekly", cost="Free",
                        domains=["Technology", "AI", "Semiconductors", "Innovation", "Manufacturing"]),

            # --- Government ---
            SourceEntry(source_id="pib_india", name="PIB India (Press Information Bureau)", category="Government",
                        reliability=0.88, update_frequency="Daily", cost="Free",
                        domains=["Government", "Government Reports", "Policy", "India", "Economy", "Defense"]),
            SourceEntry(source_id="un_data", name="UN Data Portal", category="Government",
                        reliability=0.94, update_frequency="Monthly", cost="Free",
                        domains=["Development", "Human Rights", "Health", "Climate", "Peace"]),
            SourceEntry(source_id="who", name="WHO Data API", category="Health",
                        reliability=0.95, update_frequency="Weekly", cost="Free",
                        domains=["Health", "Pandemic", "Medicine", "Public Health"]),
            SourceEntry(source_id="wto", name="WTO Statistics", category="Economic",
                        reliability=0.93, update_frequency="Monthly", cost="Free",
                        domains=["Trade", "Economy", "Tariffs", "Sanctions"]),

            # --- Climate ---
            SourceEntry(source_id="nasa", name="NASA Earth Data", category="Climate",
                        reliability=0.97, update_frequency="Daily", cost="Free",
                        domains=["Climate", "Environment", "Space", "Agriculture"]),
            SourceEntry(source_id="noaa", name="NOAA Climate Data", category="Climate",
                        reliability=0.96, update_frequency="Daily", cost="Free",
                        domains=["Climate", "Weather", "Environment", "Agriculture"]),
            SourceEntry(source_id="fao", name="FAO Food & Agriculture", category="Climate",
                        reliability=0.93, update_frequency="Monthly", cost="Free",
                        domains=["Agriculture", "Food", "Climate", "Development"]),

            # --- Clinical / Health ---
            SourceEntry(source_id="clinicaltrials", name="ClinicalTrials.gov", category="Health",
                        reliability=0.92, update_frequency="Daily", cost="Free",
                        domains=["Health", "Medicine", "Biotech", "Pharma"]),
        ]

        for entry in entries:
            self._sources[entry.source_id] = entry

        logger.info(f"Source Registry initialized with {len(self._sources)} sources.")

    def get_source(self, source_id: str) -> Optional[SourceEntry]:
        return self._sources.get(source_id)

    def get_all(self) -> List[SourceEntry]:
        return list(self._sources.values())

    def get_sources_for_domains(self, domains: List[str]) -> List[SourceEntry]:
        """Return all sources that match ANY of the given domains (case-insensitive)."""
        domains_lower = {d.lower() for d in domains}
        matched = []
        for src in self._sources.values():
            src_domains_lower = {d.lower() for d in src.domains}
            if domains_lower & src_domains_lower:
                matched.append(src)
        return self.rank_sources(matched)

    def rank_sources(self, sources: List[SourceEntry]) -> List[SourceEntry]:
        """Rank sources: highest reliability first, then lowest cost."""
        return sorted(
            sources,
            key=lambda s: (-s.reliability, _COST_RANK.get(s.cost, 9)),
        )
