"""
Contradiction Engine — Detecting Conflicting Evidence
=======================================================
The single most dangerous failure mode in geopolitical AI:

    The system stores two true facts that CONTRADICT each other,
    and treats both as valid input to analysis.

Real examples:
    - Government says "we want peace" → cooperative signal
    - Same government moves tanks to border → hostile signal
    Both are true. But they cannot BOTH drive the analysis.

    - Country A signs defense pact with Country B
    - Country A imposes sanctions on Country B
    Both are facts. But they mean something different together.

This engine detects these patterns by:
    1. Classifying observations by signal direction (cooperative / hostile)
    2. Finding same-actor pairs with opposing directions in a time window
    3. Outputting structured Contradiction records for confidence_calculator

Design rule:
    This module does NOT resolve contradictions.
    It detects them and flags them.
    Resolution is Layer 4's job (under strict grounding).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from datetime import datetime, timedelta
import logging
import sys
import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from contracts.observation import ObservationRecord, ActionType

logger = logging.getLogger("contradiction_engine")


# =====================================================================
# Signal Direction — The Foundation of Contradiction Detection
# =====================================================================

class SignalDirection(Enum):
    """Every geopolitical action has a direction on the cooperation-hostility axis."""
    COOPERATIVE = "cooperative"
    HOSTILE     = "hostile"
    NEUTRAL     = "neutral"
    INTERNAL    = "internal"     # Domestic events — no bilateral direction


# Map ActionTypes to signal directions
ACTION_DIRECTION: Dict[ActionType, SignalDirection] = {
    # Cooperative
    ActionType.COOPERATION:       SignalDirection.COOPERATIVE,
    ActionType.DIPLOMACY:         SignalDirection.COOPERATIVE,
    ActionType.AID:               SignalDirection.COOPERATIVE,
    ActionType.TRADE_AGREEMENT:   SignalDirection.COOPERATIVE,
    ActionType.CONSULTATION:      SignalDirection.COOPERATIVE,

    # Hostile
    ActionType.PRESSURE:          SignalDirection.HOSTILE,
    ActionType.SANCTION:          SignalDirection.HOSTILE,
    ActionType.TRADE_RESTRICTION: SignalDirection.HOSTILE,
    ActionType.EXPULSION:         SignalDirection.HOSTILE,
    ActionType.THREATEN_MILITARY: SignalDirection.HOSTILE,
    ActionType.MOBILIZE:          SignalDirection.HOSTILE,
    ActionType.BLOCKADE:          SignalDirection.HOSTILE,
    ActionType.CYBER_ATTACK:      SignalDirection.HOSTILE,
    ActionType.VIOLENCE:          SignalDirection.HOSTILE,
    ActionType.WAR:               SignalDirection.HOSTILE,

    # Neutral
    ActionType.STATEMENT:         SignalDirection.NEUTRAL,
    ActionType.OBSERVATION:       SignalDirection.NEUTRAL,
    ActionType.ECONOMIC_INDICATOR: SignalDirection.NEUTRAL,
    ActionType.TRADE_FLOW:        SignalDirection.NEUTRAL,
    ActionType.ARMS_TRANSFER:     SignalDirection.NEUTRAL,

    # Internal
    ActionType.PROTEST:           SignalDirection.INTERNAL,
    ActionType.COUP_ATTEMPT:      SignalDirection.INTERNAL,
    ActionType.ELECTION:          SignalDirection.INTERNAL,
    ActionType.POLICY_CHANGE:     SignalDirection.INTERNAL,
}


def get_signal_direction(action: ActionType) -> SignalDirection:
    """Get the signal direction for an action type."""
    return ACTION_DIRECTION.get(action, SignalDirection.NEUTRAL)


# =====================================================================
# Contradiction Types
# =====================================================================

class ContradictionType(Enum):
    """Taxonomy of contradictions the engine can detect."""
    RHETORIC_VS_ACTION    = "rhetoric_vs_action"     # Peace speech + mobilization
    TREATY_VS_BEHAVIOR    = "treaty_vs_behavior"     # Alliance + sanctions
    ECONOMICS_VS_POLICY   = "economics_vs_policy"    # Heavy trade + threats
    TEMPORAL_REVERSAL     = "temporal_reversal"       # Cooperation → hostility (or vice versa)
    SOURCE_DISAGREEMENT   = "source_disagreement"    # Sources disagree on same event


# =====================================================================
# Contradiction Record
# =====================================================================

@dataclass
class Contradiction:
    """
    A detected conflict between two pieces of evidence.

    This is what flows to the confidence_calculator as a penalty.
    """
    contradiction_type: ContradictionType
    observation_a: str          # obs_id of first evidence
    observation_b: str          # obs_id of second evidence
    actors: List[str]           # Actors involved
    description: str            # Human-readable explanation

    signal_a: str               # What observation A says (e.g., "cooperative diplomacy")
    signal_b: str               # What observation B says (e.g., "hostile mobilization")
    direction_a: SignalDirection = SignalDirection.NEUTRAL
    direction_b: SignalDirection = SignalDirection.NEUTRAL

    time_gap_days: float = 0.0  # Days between the two observations
    severity: float = 0.5       # 0.0 (minor) to 1.0 (critical)
    detected_at: str = ""       # When this contradiction was found

    def __post_init__(self):
        if not self.detected_at:
            self.detected_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.contradiction_type.value,
            "observation_a": self.observation_a,
            "observation_b": self.observation_b,
            "actors": self.actors,
            "description": self.description,
            "signal_a": self.signal_a,
            "signal_b": self.signal_b,
            "direction_a": self.direction_a.value,
            "direction_b": self.direction_b.value,
            "time_gap_days": self.time_gap_days,
            "severity": self.severity,
            "detected_at": self.detected_at,
        }


# =====================================================================
# Rhetoric vs Action Detection Patterns
# =====================================================================

# These action type pairs, when from the same actor in a short window,
# constitute rhetoric-vs-action contradictions.
RHETORIC_ACTION_PAIRS: List[Tuple[ActionType, ActionType]] = [
    # Words of peace + military escalation
    (ActionType.DIPLOMACY, ActionType.MOBILIZE),
    (ActionType.DIPLOMACY, ActionType.THREATEN_MILITARY),
    (ActionType.COOPERATION, ActionType.VIOLENCE),
    (ActionType.COOPERATION, ActionType.BLOCKADE),

    # Trade agreements + trade restrictions
    (ActionType.TRADE_AGREEMENT, ActionType.TRADE_RESTRICTION),
    (ActionType.TRADE_AGREEMENT, ActionType.SANCTION),

    # Aid + hostility
    (ActionType.AID, ActionType.SANCTION),
    (ActionType.AID, ActionType.PRESSURE),
]


# =====================================================================
# Contradiction Engine
# =====================================================================

class ContradictionEngine:
    """
    Scans observations for evidence that contradicts.

    Usage:
        engine = ContradictionEngine()
        contradictions = engine.detect(observations)

        for c in contradictions:
            print(f"CONTRADICTION: {c.description}")
            print(f"  Severity: {c.severity}")
    """

    def __init__(self, time_window_days: int = 30):
        """
        Args:
            time_window_days: Maximum gap between observations to consider
                             them potentially contradictory. Default 30 days.
        """
        self.time_window_days = time_window_days

    def detect(self, observations: List[ObservationRecord]) -> List[Contradiction]:
        """
        Scan observations for contradictions.

        Args:
            observations: List of ObservationRecords to check

        Returns:
            List of detected Contradiction records (may be empty)
        """
        contradictions: List[Contradiction] = []

        if len(observations) < 2:
            return contradictions

        # Phase 1: Rhetoric vs Action
        contradictions.extend(self._detect_rhetoric_vs_action(observations))

        # Phase 2: Opposing direction signals between same actors
        contradictions.extend(self._detect_directional_conflicts(observations))

        # Phase 3: Temporal reversals (cooperation → hostility within window)
        contradictions.extend(self._detect_temporal_reversals(observations))

        # Deduplicate (same pair of observations detected by multiple detectors)
        seen_pairs = set()
        unique = []
        for c in contradictions:
            pair = frozenset([c.observation_a, c.observation_b])
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                unique.append(c)

        if unique:
            logger.info(f"Detected {len(unique)} contradictions in {len(observations)} observations")

        return unique

    def detect_claim_conflicts(self, claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect contradictions on structured claims instead of raw text.

        Expected claim fields:
            actor, target, predicate, polarity, claim_id
        """
        grouped: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
        for claim in claims or []:
            actor = str(claim.get("actor") or "").strip().upper()
            target = str(claim.get("target") or "").strip().upper()
            predicate = str(claim.get("predicate") or "").strip().lower()
            if not predicate:
                continue
            key = (actor, target, predicate)
            grouped.setdefault(key, []).append(claim)

        conflicts: List[Dict[str, Any]] = []
        for (actor, target, predicate), bucket in grouped.items():
            positives = [item for item in bucket if str(item.get("polarity", "")).lower() == "positive"]
            negatives = [item for item in bucket if str(item.get("polarity", "")).lower() == "negative"]
            if not positives or not negatives:
                continue
            conflicts.append(
                {
                    "type": "claim_polarity_conflict",
                    "actor": actor,
                    "target": target,
                    "predicate": predicate,
                    "positive_claim_ids": [str(item.get("claim_id", "")) for item in positives],
                    "negative_claim_ids": [str(item.get("claim_id", "")) for item in negatives],
                    "severity": 0.7,
                }
            )
        return conflicts

    def _detect_rhetoric_vs_action(
        self, observations: List[ObservationRecord]
    ) -> List[Contradiction]:
        """Detect rhetoric vs action patterns (peace speech + mobilization)."""
        results = []

        # Index observations by actor set for efficient lookup
        by_actors: Dict[str, List[ObservationRecord]] = {}
        for obs in observations:
            if len(obs.actors) >= 1:
                # Key on sorted actors for bilateral matching
                key = "|".join(sorted(obs.actors[:2]))
                by_actors.setdefault(key, []).append(obs)

        for actor_key, actor_obs in by_actors.items():
            if len(actor_obs) < 2:
                continue

            for i in range(len(actor_obs)):
                for j in range(i + 1, len(actor_obs)):
                    obs_a, obs_b = actor_obs[i], actor_obs[j]

                    # Check time window
                    days_gap = self._days_between(obs_a.event_date, obs_b.event_date)
                    if days_gap > self.time_window_days:
                        continue

                    # Check if this pair matches any known rhetoric-action pattern
                    pair_ab = (obs_a.action_type, obs_b.action_type)
                    pair_ba = (obs_b.action_type, obs_a.action_type)

                    for pattern in RHETORIC_ACTION_PAIRS:
                        if pair_ab == pattern or pair_ba == pattern:
                            severity = self._compute_severity(obs_a, obs_b, days_gap)
                            results.append(Contradiction(
                                contradiction_type=ContradictionType.RHETORIC_VS_ACTION,
                                observation_a=obs_a.obs_id,
                                observation_b=obs_b.obs_id,
                                actors=list(set(obs_a.actors + obs_b.actors)),
                                description=(
                                    f"Rhetoric vs action: "
                                    f"'{obs_a.action_type.value}' contradicts "
                                    f"'{obs_b.action_type.value}' "
                                    f"(actors: {actor_key}, gap: {days_gap:.0f} days)"
                                ),
                                signal_a=obs_a.action_type.value,
                                signal_b=obs_b.action_type.value,
                                direction_a=get_signal_direction(obs_a.action_type),
                                direction_b=get_signal_direction(obs_b.action_type),
                                time_gap_days=days_gap,
                                severity=severity,
                            ))
                            break  # Don't double-count same pair

        return results

    def _detect_directional_conflicts(
        self, observations: List[ObservationRecord]
    ) -> List[Contradiction]:
        """
        Detect opposing direction signals between same actor pairs.

        Example: Country A sends cooperative signal to B AND hostile signal to B
                 within the time window.
        """
        results = []

        # Group by actor pair
        by_actors: Dict[str, List[ObservationRecord]] = {}
        for obs in observations:
            if len(obs.actors) >= 2:
                key = "|".join(sorted(obs.actors[:2]))
                by_actors.setdefault(key, []).append(obs)

        for actor_key, actor_obs in by_actors.items():
            # Separate into cooperative and hostile
            cooperative = [o for o in actor_obs
                          if get_signal_direction(o.action_type) == SignalDirection.COOPERATIVE]
            hostile = [o for o in actor_obs
                      if get_signal_direction(o.action_type) == SignalDirection.HOSTILE]

            if not cooperative or not hostile:
                continue

            # Find pairs within time window
            for coop in cooperative:
                for host in hostile:
                    days_gap = self._days_between(coop.event_date, host.event_date)
                    if days_gap <= self.time_window_days:
                        severity = self._compute_severity(coop, host, days_gap)
                        results.append(Contradiction(
                            contradiction_type=ContradictionType.TREATY_VS_BEHAVIOR,
                            observation_a=coop.obs_id,
                            observation_b=host.obs_id,
                            actors=list(set(coop.actors + host.actors)),
                            description=(
                                f"Directional conflict: cooperative '{coop.action_type.value}' "
                                f"vs hostile '{host.action_type.value}' "
                                f"(actors: {actor_key}, gap: {days_gap:.0f} days)"
                            ),
                            signal_a=coop.action_type.value,
                            signal_b=host.action_type.value,
                            direction_a=SignalDirection.COOPERATIVE,
                            direction_b=SignalDirection.HOSTILE,
                            time_gap_days=days_gap,
                            severity=severity,
                        ))

        return results

    def _detect_temporal_reversals(
        self, observations: List[ObservationRecord]
    ) -> List[Contradiction]:
        """
        Detect sharp reversals: a clear pattern of cooperation followed
        by hostility (or vice versa) from the same actor.
        """
        results = []

        # Group by single actor (their overall behavior)
        by_actor: Dict[str, List[ObservationRecord]] = {}
        for obs in observations:
            for actor in obs.actors[:2]:
                by_actor.setdefault(actor, []).append(obs)

        for actor, actor_obs in by_actor.items():
            if len(actor_obs) < 3:
                continue

            # Sort by event_date
            sorted_obs = sorted(actor_obs, key=lambda o: o.event_date)

            # Look for direction flips
            for i in range(1, len(sorted_obs)):
                prev = sorted_obs[i - 1]
                curr = sorted_obs[i]

                dir_prev = get_signal_direction(prev.action_type)
                dir_curr = get_signal_direction(curr.action_type)

                # Skip neutrals and internals
                if dir_prev in (SignalDirection.NEUTRAL, SignalDirection.INTERNAL):
                    continue
                if dir_curr in (SignalDirection.NEUTRAL, SignalDirection.INTERNAL):
                    continue

                # Check for flip
                if dir_prev != dir_curr:
                    days_gap = self._days_between(prev.event_date, curr.event_date)
                    if days_gap <= self.time_window_days:
                        # Severity: closer reversals are more suspicious
                        severity = min(1.0, 0.3 + (1.0 - days_gap / self.time_window_days) * 0.5)
                        # Only high-intensity reversals matter
                        severity *= max(prev.intensity, curr.intensity)

                        if severity >= 0.3:  # Threshold to avoid noise
                            results.append(Contradiction(
                                contradiction_type=ContradictionType.TEMPORAL_REVERSAL,
                                observation_a=prev.obs_id,
                                observation_b=curr.obs_id,
                                actors=[actor],
                                description=(
                                    f"Temporal reversal by {actor}: "
                                    f"'{prev.action_type.value}' ({dir_prev.value}) -> "
                                    f"'{curr.action_type.value}' ({dir_curr.value}) "
                                    f"in {days_gap:.0f} days"
                                ),
                                signal_a=prev.action_type.value,
                                signal_b=curr.action_type.value,
                                direction_a=dir_prev,
                                direction_b=dir_curr,
                                time_gap_days=days_gap,
                                severity=round(severity, 4),
                            ))

        return results

    def _compute_severity(
        self,
        obs_a: ObservationRecord,
        obs_b: ObservationRecord,
        days_gap: float,
    ) -> float:
        """
        Compute contradiction severity (0.0—1.0).

        Higher severity when:
            - Time gap is small (same-day contradiction is worst)
            - Both observations are high intensity
            - Both observations are high confidence
        """
        # Time factor: closer = more severe
        time_factor = 1.0 - (days_gap / max(self.time_window_days, 1))

        # Intensity factor: average intensity of both
        intensity_factor = (obs_a.intensity + obs_b.intensity) / 2.0

        # Confidence factor: average confidence of both
        confidence_factor = (obs_a.confidence + obs_b.confidence) / 2.0

        severity = (
            0.4 * time_factor +
            0.35 * intensity_factor +
            0.25 * confidence_factor
        )
        return round(min(1.0, max(0.0, severity)), 4)

    def _days_between(self, date_a: str, date_b: str) -> float:
        """Compute absolute days between two date strings."""
        try:
            da = datetime.strptime(date_a[:10], "%Y-%m-%d")
            db = datetime.strptime(date_b[:10], "%Y-%m-%d")
            return abs((da - db).total_seconds() / 86400)
        except (ValueError, TypeError):
            return 999.0  # If dates can't be parsed, assume far apart


# =====================================================================
# Module-Level Singleton
# =====================================================================

contradiction_engine = ContradictionEngine()

__all__ = [
    "ContradictionEngine", "contradiction_engine",
    "Contradiction", "ContradictionType",
    "SignalDirection", "get_signal_direction",
    "ACTION_DIRECTION",
]
