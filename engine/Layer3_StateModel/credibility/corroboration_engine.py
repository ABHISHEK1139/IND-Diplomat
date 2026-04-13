"""
Corroboration Engine — Multi-Source Verification
===================================================
The most basic rule in intelligence analysis:

    One source = rumor.
    Two independent sources = signal.
    Three+ sources = probable fact.

Without this, a single MoltBot scraping error or a single
GDELT misclassification pollutes the entire reasoning chain.

This engine:
    1. Groups observations by what they describe (same event/claim)
    2. Counts how many INDEPENDENT sources confirm each claim
    3. Assigns a corroboration score that flows to confidence_calculator

"Independent" means:
    - Different source types (GDELT + WorldBank, not GDELT + GDELT)
    - Or different source instances of the same type
      with significantly different raw_references

Design rule:
    This module does NOT decide truth.
    It measures evidentiary support.
    A well-corroborated claim CAN still be wrong.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Set, Tuple
from datetime import datetime
import logging
import sys
import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from contracts.observation import ObservationRecord

logger = logging.getLogger("corroboration_engine")


# =====================================================================
# Corroboration Levels
# =====================================================================

CORROBORATION_THRESHOLDS = {
    "unverified":     0,    # No additional sources
    "single_source":  1,    # Only 1 source
    "corroborated":   2,    # 2 independent sources
    "well_supported": 3,    # 3+ independent sources
}


# =====================================================================
# Corroboration Result
# =====================================================================

@dataclass
class CorroborationResult:
    """
    Assessment of how well a claim/event is supported by multiple sources.
    """
    claim_key: str                      # What claim/event this is about
    observation_ids: List[str] = field(default_factory=list)  # Supporting obs IDs
    sources: List[str] = field(default_factory=list)          # Unique sources
    source_types: List[str] = field(default_factory=list)     # Unique source types
    independent_count: int = 0          # Number of truly independent sources
    score: float = 0.0                  # 0.0 (unverified) to 1.0 (strong)
    level: str = "unverified"           # Human-readable level
    actors: List[str] = field(default_factory=list)
    event_date: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_key": self.claim_key,
            "observation_ids": self.observation_ids,
            "sources": self.sources,
            "source_types": self.source_types,
            "independent_count": self.independent_count,
            "score": round(self.score, 4),
            "level": self.level,
            "actors": self.actors,
            "event_date": self.event_date,
        }


# =====================================================================
# Corroboration Engine
# =====================================================================

class CorroborationEngine:
    """
    Checks how many independent sources support each claim.

    Usage:
        engine = CorroborationEngine()
        results = engine.assess(observations)

        for r in results:
            if r.level == "unverified":
                print(f"WARNING: {r.claim_key} only has 1 source")
    """

    def __init__(
        self,
        min_for_signal: int = 2,
        time_window_days: int = 7,
    ):
        """
        Args:
            min_for_signal: Minimum independent sources to consider a claim credible
            time_window_days: Maximum gap between observations to consider them
                             describing the same event
        """
        self.min_for_signal = min_for_signal
        self.time_window_days = time_window_days

    def assess(
        self, observations: List[ObservationRecord]
    ) -> List[CorroborationResult]:
        """
        Assess corroboration for all observations.

        Groups observations by claim (action + actors + approximate date),
        counts independent sources per group.

        Args:
            observations: Full set of observations to cross-check

        Returns:
            List of CorroborationResult, one per claim group
        """
        # Step 1: Group observations by what they describe
        groups = self._group_by_claim(observations)

        # Step 2: Assess each group
        results = []
        for claim_key, obs_list in groups.items():
            result = self._assess_group(claim_key, obs_list)
            results.append(result)

        return results

    def assess_claims(self, claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Assess corroboration on structured claim objects.
        """
        groups: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = {}
        for claim in claims or []:
            key = (
                str(claim.get("actor") or "").upper(),
                str(claim.get("target") or "").upper(),
                str(claim.get("predicate") or "").lower(),
                str(claim.get("polarity") or "neutral").lower(),
            )
            groups.setdefault(key, []).append(claim)

        results: List[Dict[str, Any]] = []
        for key, bucket in groups.items():
            sources = {
                str((item.get("metadata") or {}).get("source") or "").lower()
                for item in bucket
            }
            sources.discard("")
            source_count = len(sources)
            if source_count >= 3:
                score = 1.0
            elif source_count == 2:
                score = 0.75
            elif source_count == 1:
                score = 0.35
            else:
                score = 0.2
            results.append(
                {
                    "actor": key[0],
                    "target": key[1],
                    "predicate": key[2],
                    "polarity": key[3],
                    "source_count": source_count,
                    "sources": sorted(sources),
                    "score": score,
                }
            )
        return results

    def get_corroboration_for_observation(
        self,
        obs: ObservationRecord,
        all_observations: List[ObservationRecord],
    ) -> CorroborationResult:
        """
        Get corroboration score for a specific observation
        by checking it against all other observations.
        """
        # Find matching observations (same claim)
        matching = [obs]
        for other in all_observations:
            if other.obs_id == obs.obs_id:
                continue
            if self._same_claim(obs, other):
                matching.append(other)

        claim_key = self._make_claim_key(obs)
        return self._assess_group(claim_key, matching)

    def _group_by_claim(
        self, observations: List[ObservationRecord]
    ) -> Dict[str, List[ObservationRecord]]:
        """
        Group observations by what real-world event they describe.

        Claim key = action_type + sorted actors + date bucket.
        """
        groups: Dict[str, List[ObservationRecord]] = {}

        for obs in observations:
            key = self._make_claim_key(obs)

            # Check if this observation matches an existing group
            placed = False
            for existing_key, existing_obs_list in groups.items():
                # Check if keys match (same event type + actors + date window)
                if self._keys_match(key, existing_key):
                    existing_obs_list.append(obs)
                    placed = True
                    break

            if not placed:
                groups[key] = [obs]

        return groups

    def _make_claim_key(self, obs: ObservationRecord) -> str:
        """Generate a claim key for grouping."""
        actors = "|".join(sorted(obs.actors[:2])) if obs.actors else "NONE"
        # Bucket date to week level for grouping
        date_bucket = obs.event_date[:7] if obs.event_date else "UNKNOWN"  # YYYY-MM
        return f"{obs.action_type.value}:{actors}:{date_bucket}"

    def _keys_match(self, key_a: str, key_b: str) -> bool:
        """Check if two claim keys describe the same event."""
        parts_a = key_a.split(":")
        parts_b = key_b.split(":")

        if len(parts_a) != 3 or len(parts_b) != 3:
            return key_a == key_b

        # Same action type and same actors
        return parts_a[0] == parts_b[0] and parts_a[1] == parts_b[1]

    def _same_claim(self, obs_a: ObservationRecord, obs_b: ObservationRecord) -> bool:
        """Check if two observations describe the same real-world event."""
        # Same action type
        if obs_a.action_type != obs_b.action_type:
            return False

        # Same actors (at least overlap)
        actors_a = set(obs_a.actors)
        actors_b = set(obs_b.actors)
        if not actors_a.intersection(actors_b):
            return False

        # Within time window
        days = self._days_between(obs_a.event_date, obs_b.event_date)
        if days > self.time_window_days:
            return False

        return True

    def _assess_group(
        self, claim_key: str, obs_list: List[ObservationRecord]
    ) -> CorroborationResult:
        """Assess corroboration for a group of observations."""
        if not obs_list:
            return CorroborationResult(claim_key=claim_key)

        # Count unique sources and source types
        unique_sources: Set[str] = set()
        unique_source_types: Set[str] = set()
        unique_references: Set[str] = set()
        all_actors: Set[str] = set()
        obs_ids: List[str] = []

        for obs in obs_list:
            unique_sources.add(obs.source.lower())
            unique_source_types.add(obs.source_type.value)
            if obs.raw_reference:
                unique_references.add(obs.raw_reference)
            all_actors.update(obs.actors)
            obs_ids.append(obs.obs_id)

        # Independent count = unique source types
        # (GDELT + WorldBank = 2, GDELT + GDELT from different URLs = 1.5)
        independent_count = len(unique_source_types)

        # Bonus for same-type but different references
        if len(unique_sources) == 1 and len(unique_references) > 1:
            independent_count = max(independent_count, 1.5)

        # Compute score
        if independent_count >= 3:
            score = 1.0
            level = "well_supported"
        elif independent_count >= 2:
            score = 0.75
            level = "corroborated"
        elif independent_count >= 1.5:
            score = 0.5
            level = "partially_corroborated"
        elif len(obs_list) >= 2:
            score = 0.4
            level = "single_source"  # Multiple observations but same source type
        else:
            score = 0.2
            level = "unverified"

        return CorroborationResult(
            claim_key=claim_key,
            observation_ids=obs_ids,
            sources=sorted(unique_sources),
            source_types=sorted(unique_source_types),
            independent_count=int(independent_count),
            score=score,
            level=level,
            actors=sorted(all_actors),
            event_date=obs_list[0].event_date if obs_list else "",
        )

    def _days_between(self, date_a: str, date_b: str) -> float:
        """Compute absolute days between two date strings."""
        try:
            da = datetime.strptime(date_a[:10], "%Y-%m-%d")
            db = datetime.strptime(date_b[:10], "%Y-%m-%d")
            return abs((da - db).total_seconds() / 86400)
        except (ValueError, TypeError):
            return 999.0


# =====================================================================
# Module-Level Singleton
# =====================================================================

corroboration_engine = CorroborationEngine()

__all__ = [
    "CorroborationEngine", "corroboration_engine",
    "CorroborationResult",
    "CORROBORATION_THRESHOLDS",
]
