"""
Source Registry — Provenance & Reliability System
=================================================
Layer 2 Rule: Every piece of evidence must carry its trust rating.

This module does NOT decide what to trust (that's Layer 3 reasoning).
It provides the raw trust metadata for Layer 3 to use in weighted reasoning.

Three confidence dimensions per evidence:
    1. confidence_source   — how reliable is this data source?
    2. confidence_time     — how recent is this data? (temporal decay)
    3. confidence_consensus — how many independent sources agree?
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# Source Trust Ratings
# ═══════════════════════════════════════════════════════════════
# These are hard-coded trust weights based on source nature.
# Official statistics > Academic datasets > Event data > News > Scraped
#
# NOTE: These weights are DESCRIPTIVE, not PRESCRIPTIVE.
# Layer 3 may override them based on analysis context.

SOURCE_TRUST: Dict[str, float] = {
    # Official statistics (highest trust)
    "world_bank":          0.95,
    "imf":                 0.95,
    "un_comtrade":         0.90,
    "census":              0.95,

    # Academic/curated datasets
    "sipri":               0.90,
    "v_dem":               0.85,
    "atop":                0.85,
    "correlates_of_war":   0.85,

    # Structured event data
    "gdelt":               0.70,
    "acled":               0.80,
    "icews":               0.75,

    # Legal/official documents
    "treaties":            0.95,
    "un_resolutions":      0.90,
    "sanctions_lists":     0.95,
    "govt_statements":     0.80,

    # News media
    "news_reuters":        0.75,
    "news_ap":             0.75,
    "news_bbc":            0.70,
    "news_generic":        0.50,
    "news_state_media":    0.35,

    # Scraped/unverified
    "scraped_statement":   0.60,
    "scraped_report":      0.50,
    "social_media":        0.30,
    "moltbot_scrape":      0.40,
    "unknown":             0.20,
}


class SourceCategory(Enum):
    """Broad categories for source classification."""
    OFFICIAL = "official"          # Government/IO statistics
    ACADEMIC = "academic"          # Peer-reviewed datasets
    EVENT_DATA = "event_data"      # Structured event feeds
    LEGAL = "legal"                # Treaties, resolutions
    NEWS = "news"                  # Media reporting
    SCRAPED = "scraped"            # Web scraping, unverified
    UNKNOWN = "unknown"

# Map each source to its category
SOURCE_CATEGORIES: Dict[str, SourceCategory] = {
    "world_bank": SourceCategory.OFFICIAL,
    "imf": SourceCategory.OFFICIAL,
    "un_comtrade": SourceCategory.OFFICIAL,
    "census": SourceCategory.OFFICIAL,
    "sipri": SourceCategory.ACADEMIC,
    "v_dem": SourceCategory.ACADEMIC,
    "atop": SourceCategory.ACADEMIC,
    "correlates_of_war": SourceCategory.ACADEMIC,
    "gdelt": SourceCategory.EVENT_DATA,
    "acled": SourceCategory.EVENT_DATA,
    "icews": SourceCategory.EVENT_DATA,
    "treaties": SourceCategory.LEGAL,
    "un_resolutions": SourceCategory.LEGAL,
    "sanctions_lists": SourceCategory.LEGAL,
    "govt_statements": SourceCategory.LEGAL,
    "news_reuters": SourceCategory.NEWS,
    "news_ap": SourceCategory.NEWS,
    "news_bbc": SourceCategory.NEWS,
    "news_generic": SourceCategory.NEWS,
    "news_state_media": SourceCategory.NEWS,
    "scraped_statement": SourceCategory.SCRAPED,
    "scraped_report": SourceCategory.SCRAPED,
    "social_media": SourceCategory.SCRAPED,
    "moltbot_scrape": SourceCategory.SCRAPED,
    "unknown": SourceCategory.UNKNOWN,
}


@dataclass
class EvidenceProvenance:
    """
    Provenance record attached to every piece of evidence.

    Example:
        EvidenceProvenance(
            source="gdelt",
            confidence_source=0.70,
            confidence_time=0.82,    # from temporal_reasoner
            confidence_consensus=0.6, # 2 sources agree
            combined_confidence=0.71, # weighted average
        )
    """
    source: str
    raw_data_id: Optional[str] = None       # Original record ID
    retrieval_date: Optional[str] = None    # When we fetched this
    fact_date: Optional[str] = None         # When the fact occurred

    # Three confidence dimensions
    confidence_source: float = 0.5          # Trust in the data source
    confidence_time: float = 1.0            # Temporal freshness (decay)
    confidence_consensus: float = 0.5       # Multi-source agreement

    # Combined score (computed)
    combined_confidence: float = 0.0

    # Lineage tracking
    source_url: Optional[str] = None
    corroborating_sources: List[str] = field(default_factory=list)

    def compute_combined(self, weights: Dict[str, float] = None) -> float:
        """
        Compute combined confidence from the three dimensions.

        Default weights:
            source: 0.4   — how reliable is this source type?
            time: 0.35    — how fresh is this data?
            consensus: 0.25 — how many sources agree?
        """
        if weights is None:
            weights = {
                "source": 0.40,
                "time": 0.35,
                "consensus": 0.25,
            }

        self.combined_confidence = round(
            weights["source"] * self.confidence_source
            + weights["time"] * self.confidence_time
            + weights["consensus"] * self.confidence_consensus,
            4,
        )
        return self.combined_confidence


class SourceRegistry:
    """
    Registry for looking up source trust metadata.

    Usage:
        registry = source_registry  # module-level singleton
        trust = registry.get_trust("gdelt")        # → 0.70
        cat = registry.get_category("world_bank")   # → SourceCategory.OFFICIAL
        prov = registry.create_provenance(
            source="gdelt",
            fact_date="2024-02-01",
            confidence_time=0.82,
        )
    """

    def get_trust(self, source: str) -> float:
        """Get trust weight for a source (case-insensitive)."""
        return SOURCE_TRUST.get(source.lower(), SOURCE_TRUST["unknown"])

    def get_category(self, source: str) -> SourceCategory:
        """Get category for a source."""
        return SOURCE_CATEGORIES.get(source.lower(), SourceCategory.UNKNOWN)

    def create_provenance(
        self,
        source: str,
        fact_date: str = None,
        confidence_time: float = 1.0,
        confidence_consensus: float = 0.5,
        source_url: str = None,
        corroborating: List[str] = None,
    ) -> EvidenceProvenance:
        """
        Create a provenance record for an evidence item.

        Args:
            source: Data source name (e.g., "gdelt", "world_bank")
            fact_date: When the fact occurred (ISO format)
            confidence_time: Temporal decay weight (from temporal_reasoner)
            confidence_consensus: Multi-source agreement score
            source_url: Original URL of the data
            corroborating: List of other sources that agree

        Returns:
            EvidenceProvenance with computed combined confidence.
        """
        import datetime
        prov = EvidenceProvenance(
            source=source.lower(),
            fact_date=fact_date,
            retrieval_date=datetime.datetime.now().strftime("%Y-%m-%d"),
            confidence_source=self.get_trust(source),
            confidence_time=confidence_time,
            confidence_consensus=confidence_consensus,
            source_url=source_url,
            corroborating_sources=corroborating or [],
        )
        prov.compute_combined()
        return prov

    def list_sources(self, category: SourceCategory = None) -> List[str]:
        """List all registered sources, optionally filtered by category."""
        if category is None:
            return list(SOURCE_TRUST.keys())
        return [
            src for src, cat in SOURCE_CATEGORIES.items()
            if cat == category
        ]


# ═══════════════════════════════════════════════════════════════
# Module-level Singleton
# ═══════════════════════════════════════════════════════════════
source_registry = SourceRegistry()

__all__ = [
    "SourceRegistry", "source_registry",
    "EvidenceProvenance", "SOURCE_TRUST",
    "SourceCategory", "SOURCE_CATEGORIES",
]
