"""
Freshness Model — Evidence Recency Weighting
===============================================
Extends the temporal_reasoner with a key distinction:

    temporal_reasoner answers: "Is this fact still valid?"
    freshness_model   answers: "How much should this influence TODAY's analysis?"

These are different questions:
    - A 1991 treaty may be VALID (temporal_reasoner says yes)
      but nearly IRRELEVANT to today's crisis (freshness says low weight)

    - Yesterday's GDELT event may have EXPIRED from the 24h cycle
      but is HIGHLY RELEVANT to current tension (freshness says high weight)

Design:
    Per-source decay curves with different half-lives.
    GDELT events decay fast (days), treaties decay slow (years).
    Economic indicators follow annual cycles.

    freshness_score = e^(-λ × days_since) where λ = ln(2) / half_life
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import math
import logging
import sys
import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from contracts.observation import ObservationRecord

logger = logging.getLogger("freshness_model")


# =====================================================================
# Source-Specific Decay Configuration
# =====================================================================
# Half-life: days until the evidence's influence drops to 50%
# Context: how fast does this type of information become stale?
#
# Event data (GDELT): becomes irrelevant within weeks
# Treaties: remain relevant for years (but slowly lose weight)
# Economic data: annual cycle, moderate decay
# Military data: months-level relevance
# News: very fast decay
# Scraped: fastest decay — least reliable over time

SOURCE_HALF_LIVES: Dict[str, float] = {
    # Event monitors — rapid decay
    "gdelt":              7.0,       # 7-day half-life (1 week)
    "acled":             14.0,       # 14-day half-life (2 weeks)
    "icews":             10.0,       # 10-day half-life

    # Official statistics — slow decay
    "world_bank":       365.0,       # 1-year half-life (annual data)
    "imf":              365.0,       # 1-year half-life
    "un_comtrade":      365.0,       # 1-year half-life

    # Academic/curated — very slow decay
    "sipri":            730.0,       # 2-year half-life (def spending)
    "v_dem":            730.0,       # 2-year half-life
    "atop":            1825.0,       # 5-year half-life (alliances)
    "correlates_of_war": 1825.0,     # 5-year half-life

    # Legal — extremely slow decay (but not zero)
    "treaties":        3650.0,       # 10-year half-life
    "un_resolutions":  1825.0,       # 5-year half-life
    "sanctions_lists":  365.0,       # 1-year (active sanctions change)

    # News — fast decay
    "news_reuters":       3.0,       # 3-day half-life
    "news_ap":            3.0,
    "news_bbc":           3.0,
    "news_generic":       2.0,
    "news_state_media":   2.0,

    # Government statements — moderate
    "govt_statements":   30.0,       # 30-day half-life

    # Scraped/unverified — fastest decay
    "scraped_statement":  2.0,
    "scraped_report":     3.0,
    "social_media":       1.0,       # 1-day half-life
    "moltbot_scrape":     3.0,

    # Unknown
    "unknown":            1.0,
}

# Minimum freshness score (even very old data gets this minimum)
MIN_FRESHNESS = 0.01

# Maximum age (beyond this, freshness is clamped to MIN_FRESHNESS)
MAX_AGE_DAYS = 7300  # 20 years


# =====================================================================
# Freshness Score Record
# =====================================================================

@dataclass
class FreshnessScore:
    """
    Freshness assessment for a single piece of evidence.
    """
    obs_id: str
    source: str
    event_date: str
    reference_date: str          # "Today" for the analysis
    days_since: float
    half_life: float
    raw_score: float             # The exponential decay value
    clamped_score: float         # After applying min/max
    category: str                # "current", "recent", "aging", "stale", "historical"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "obs_id": self.obs_id,
            "source": self.source,
            "event_date": self.event_date,
            "days_since": round(self.days_since, 1),
            "half_life": self.half_life,
            "score": round(self.clamped_score, 4),
            "category": self.category,
        }


# =====================================================================
# Freshness Scorer
# =====================================================================

class FreshnessScorer:
    """
    Computes freshness scores for observations.

    Usage:
        scorer = FreshnessScorer()

        # Single observation
        score = scorer.score(observation, reference_date="2026-02-15")

        # Batch with weighted filtering
        scored = scorer.score_batch(observations, reference_date="2026-02-15")
        fresh = [s for s in scored if s.category != "stale"]
    """

    def __init__(self, half_lives: Dict[str, float] = None):
        self.half_lives = half_lives or SOURCE_HALF_LIVES

    def score(
        self,
        obs: ObservationRecord,
        reference_date: str = None,
    ) -> FreshnessScore:
        """
        Compute freshness score for a single observation.

        Args:
            obs: The observation to score
            reference_date: "Today" for the analysis (default: actual today)

        Returns:
            FreshnessScore with computed decay
        """
        if reference_date is None:
            reference_date = datetime.now().strftime("%Y-%m-%d")

        days_since = self._days_since(obs.event_date, reference_date)
        half_life = self.half_lives.get(obs.source.lower(), 7.0)

        # Compute exponential decay: e^(-λ × days)
        # where λ = ln(2) / half_life
        if half_life > 0 and days_since >= 0:
            lambda_param = math.log(2) / half_life
            raw_score = math.exp(-lambda_param * days_since)
        else:
            raw_score = 1.0  # Future date or zero half-life → full freshness

        # Clamp
        clamped = max(MIN_FRESHNESS, min(1.0, raw_score))
        if days_since > MAX_AGE_DAYS:
            clamped = MIN_FRESHNESS

        # Categorize
        category = self._categorize(clamped)

        return FreshnessScore(
            obs_id=obs.obs_id,
            source=obs.source,
            event_date=obs.event_date,
            reference_date=reference_date,
            days_since=days_since,
            half_life=half_life,
            raw_score=round(raw_score, 6),
            clamped_score=round(clamped, 6),
            category=category,
        )

    def score_batch(
        self,
        observations: List[ObservationRecord],
        reference_date: str = None,
    ) -> List[FreshnessScore]:
        """Score a batch of observations."""
        return [self.score(obs, reference_date) for obs in observations]

    def filter_fresh(
        self,
        observations: List[ObservationRecord],
        min_score: float = 0.1,
        reference_date: str = None,
    ) -> List[ObservationRecord]:
        """Return only observations above a freshness threshold."""
        scored = self.score_batch(observations, reference_date)
        fresh_ids = {s.obs_id for s in scored if s.clamped_score >= min_score}
        return [obs for obs in observations if obs.obs_id in fresh_ids]

    def weight_observations(
        self,
        observations: List[ObservationRecord],
        reference_date: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Return observations paired with their freshness weights.

        Returns:
            List of {"observation": ObservationRecord, "freshness": FreshnessScore}
        """
        scored = self.score_batch(observations, reference_date)
        return [
            {"observation": obs, "freshness": score}
            for obs, score in zip(observations, scored)
        ]

    def _categorize(self, score: float) -> str:
        """Categorize a freshness score into human-readable buckets."""
        if score >= 0.8:
            return "current"       # Very recent, high influence
        elif score >= 0.5:
            return "recent"        # Still quite relevant
        elif score >= 0.2:
            return "aging"         # Losing relevance
        elif score >= 0.05:
            return "stale"         # Should be used with caution
        else:
            return "historical"    # Nearly irrelevant to current analysis

    def _days_since(self, event_date: str, reference_date: str) -> float:
        """Compute days between event_date and reference_date."""
        try:
            ev = datetime.strptime(event_date[:10], "%Y-%m-%d")
            ref = datetime.strptime(reference_date[:10], "%Y-%m-%d")
            return max(0.0, (ref - ev).total_seconds() / 86400)
        except (ValueError, TypeError):
            return 365.0  # If unparseable, assume 1 year old

    def get_half_life(self, source: str) -> float:
        """Get the half-life for a source."""
        return self.half_lives.get(source.lower(), 7.0)


# =====================================================================
# Module-Level Singleton
# =====================================================================

freshness_scorer = FreshnessScorer()

__all__ = [
    "FreshnessScorer", "freshness_scorer",
    "FreshnessScore",
    "SOURCE_HALF_LIVES",
    "MIN_FRESHNESS", "MAX_AGE_DAYS",
]
