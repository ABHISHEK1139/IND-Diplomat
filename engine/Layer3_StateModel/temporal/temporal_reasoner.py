"""
Temporal Reasoner — The Time Engine
====================================
Every piece of information ages differently.

- A GDELT protest from last week: HIGH influence
- A GDELT protest from 4 years ago: ZERO influence
- A treaty from 1995: depends on status (active/expired/replaced)
- GDP data from 2 years ago: still relevant

This module decides:
    1. Is this fact still valid?
    2. How much does it influence the present?
    3. Should it be included in the current state vector?

Design Principle:
    You don't fix hallucination at the LLM.
    You fix hallucination BEFORE the LLM by filtering out stale data.

Pipeline position:
    Layer-2 Signals → TEMPORAL REASONER → Layer-3 State Builder → API → MoltBot
"""

import math
import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


# ══════════════════════════════════════════════════════════════════
# Document Lifecycle States
# ══════════════════════════════════════════════════════════════════

class DocumentStatus(Enum):
    """Legal/factual validity states for knowledge objects."""
    ACTIVE = "active"           # Currently in force
    SUSPENDED = "suspended"     # Temporarily halted
    EXPIRED = "expired"         # Ended by time clause
    REPLACED = "replaced"       # Superseded by newer version
    VIOLATED = "violated"       # Exists but not respected
    WITHDRAWN = "withdrawn"     # Unilaterally pulled out
    PENDING = "pending"         # Not yet in force


# ══════════════════════════════════════════════════════════════════
# Time Decay Rules Table
# ══════════════════════════════════════════════════════════════════
# Each data source has its own "memory length".
# This is how long data from that source remains influential.
#
# The decay function is exponential:
#   weight = e^(-λ * days_since)
#
# Where λ = ln(2) / half_life_days
# (half_life = days until influence drops to 50%)

@dataclass
class DecayRule:
    """Time decay configuration for a data source."""
    source: str
    half_life_days: float       # Days until 50% influence
    min_weight: float           # Floor (below this → discard)
    max_age_days: float         # Hard cutoff (older → always discard)
    description: str = ""

    @property
    def lambda_param(self) -> float:
        """Compute decay rate λ = ln(2) / half_life."""
        if self.half_life_days <= 0:
            return 0.0
        return math.log(2) / self.half_life_days


# ══════════════════════════════════════════════════════════════════
# THE RULES TABLE
# ══════════════════════════════════════════════════════════════════
# This table controls the entire temporal behavior of the system.
# Tuning these values changes how the system weighs past vs. present.

DECAY_RULES: Dict[str, DecayRule] = {
    # ── Events (fast decay) ──
    "GDELT": DecayRule(
        source="GDELT",
        half_life_days=7,          # 50% influence after 1 week
        min_weight=0.05,           # Below 5% → ignore
        max_age_days=90,           # 3 months hard cutoff
        description="Real-time events decay fast. A protest last week matters; 4 years ago doesn't.",
    ),

    # ── Military (slow decay) ──
    "SIPRI": DecayRule(
        source="SIPRI",
        half_life_days=365,        # 50% influence after 1 year
        min_weight=0.10,
        max_age_days=3650,         # 10 year hard cutoff
        description="Military spending trends are slow-moving. A procurement from 3 years ago still signals intent.",
    ),

    # ── Economic (moderate decay) ──
    "WorldBank": DecayRule(
        source="WorldBank",
        half_life_days=180,        # 50% after 6 months
        min_weight=0.10,
        max_age_days=2555,         # ~7 years
        description="GDP, inflation, debt: recent data dominates but historical trends matter.",
    ),

    # ── Sanctions (slow decay) ──
    "Sanctions": DecayRule(
        source="Sanctions",
        half_life_days=365,        # 50% after 1 year
        min_weight=0.15,
        max_age_days=1825,         # 5 years
        description="Sanctions are legal instruments. They remain potent until explicitly lifted.",
    ),

    # ── Democracy Index (very slow decay) ──
    "V-Dem": DecayRule(
        source="V-Dem",
        half_life_days=730,        # 50% after 2 years
        min_weight=0.15,
        max_age_days=3650,         # 10 years
        description="Political systems change slowly. A democracy score from 3 years ago is still informative.",
    ),

    # ── Alliances (very slow decay) ──
    "ATOP": DecayRule(
        source="ATOP",
        half_life_days=1825,       # 50% after 5 years
        min_weight=0.20,
        max_age_days=7300,         # 20 years
        description="Alliances are structural. NATO from 1949 still applies.",
    ),

    # ── Treaties (no decay — use status instead) ──
    "Treaties": DecayRule(
        source="Treaties",
        half_life_days=36500,      # ~100 years (effectively no decay)
        min_weight=0.10,
        max_age_days=36500,
        description="Treaties don't decay by time. They have a STATUS (active/expired/replaced).",
    ),

    # ── Leaders (moderate decay) ──
    "Leaders": DecayRule(
        source="Leaders",
        half_life_days=90,         # 50% after 3 months
        min_weight=0.10,
        max_age_days=730,          # 2 years
        description="Leadership behavior is recent. An approval rating from 2 years ago is stale.",
    ),
}


# ══════════════════════════════════════════════════════════════════
# Temporal Validity Record
# ══════════════════════════════════════════════════════════════════

@dataclass
class TemporalRecord:
    """
    A fact with temporal metadata.
    This wraps any piece of data with validity and decay information.
    """
    data: Any                          # The actual content
    source: str                        # Data source (GDELT, SIPRI, etc.)
    fact_date: str                     # When this fact was true (YYYY-MM-DD)
    valid_from: Optional[str] = None   # Start of validity (for treaties)
    valid_to: Optional[str] = None     # End of validity (for treaties)
    status: DocumentStatus = DocumentStatus.ACTIVE
    replaced_by: Optional[str] = None  # ID of superseding document


# ══════════════════════════════════════════════════════════════════
# The Temporal Reasoner
# ══════════════════════════════════════════════════════════════════

class TemporalReasoner:
    """
    Decides which facts are still valid and how much they influence the present.

    Usage:
        reasoner = TemporalReasoner()

        # Compute how much a GDELT event from 14 days ago matters today:
        weight = reasoner.compute_decay("GDELT", days_ago=14)
        # → ~0.25 (quarter influence)

        # Filter a list of records to only include still-valid ones:
        valid = reasoner.filter_valid(records, reference_date="2026-02-14")

        # Apply decay weights to a set of signals:
        weighted = reasoner.apply_decay(signals, reference_date="2026-02-14")
    """

    def __init__(self, rules: Dict[str, DecayRule] = None):
        self.rules = rules or DECAY_RULES

    # ──────────────────────────────────────────────────────────────
    # Core: Compute Time Decay Weight
    # ──────────────────────────────────────────────────────────────
    def compute_decay(self, source: str, days_ago: float) -> float:
        """
        Compute the influence weight of a fact from `days_ago` days.

        Returns:
            float between 0.0 (irrelevant) and 1.0 (fully current)
        """
        rule = self.rules.get(source)
        if rule is None:
            # Unknown source: use moderate default
            rule = DecayRule(source=source, half_life_days=30,
                             min_weight=0.10, max_age_days=365)

        # Hard cutoff
        if days_ago > rule.max_age_days:
            return 0.0

        # Exponential decay: weight = e^(-λ * t)
        weight = math.exp(-rule.lambda_param * days_ago)

        # Floor
        if weight < rule.min_weight:
            return 0.0

        return round(weight, 4)

    # ──────────────────────────────────────────────────────────────
    # Compute Days Since
    # ──────────────────────────────────────────────────────────────
    def _days_since(self, fact_date: str, reference_date: str = None) -> float:
        """Calculate days between fact_date and reference_date."""
        if reference_date is None:
            ref = datetime.datetime.now()
        else:
            ref = datetime.datetime.strptime(reference_date, "%Y-%m-%d")

        try:
            fact = datetime.datetime.strptime(fact_date, "%Y-%m-%d")
        except ValueError:
            try:
                fact = datetime.datetime.strptime(fact_date, "%Y%m%d")
            except ValueError:
                return 9999  # Unknown date → treat as very old

        delta = (ref - fact).days
        return max(0, delta)

    # ──────────────────────────────────────────────────────────────
    # Check Document Validity (for treaties/legal documents)
    # ──────────────────────────────────────────────────────────────
    def is_valid(self, record: TemporalRecord, reference_date: str = None) -> bool:
        """
        Check if a document/fact is currently valid.

        Rules:
        - ACTIVE: valid
        - SUSPENDED/VIOLATED: valid but flagged
        - EXPIRED/REPLACED/WITHDRAWN: invalid
        - Check valid_from/valid_to date range
        """
        # Status check
        if record.status in (
            DocumentStatus.EXPIRED,
            DocumentStatus.REPLACED,
            DocumentStatus.WITHDRAWN,
        ):
            return False

        if record.status == DocumentStatus.PENDING:
            return False  # Not yet in force

        # Date range check
        if reference_date is None:
            ref = datetime.datetime.now().strftime("%Y-%m-%d")
        else:
            ref = reference_date

        if record.valid_from and ref < record.valid_from:
            return False  # Not yet valid

        if record.valid_to and ref > record.valid_to:
            return False  # Expired

        return True

    # ──────────────────────────────────────────────────────────────
    # Filter: Only Keep Valid & Influential Records
    # ──────────────────────────────────────────────────────────────
    def filter_valid(
        self,
        records: List[TemporalRecord],
        reference_date: str = None,
    ) -> List[Dict]:
        """
        Filter records to only return currently valid and influential ones.

        Returns list of dicts with:
            {"record": TemporalRecord, "weight": float, "days_ago": float}
        """
        results = []
        for rec in records:
            # Step 1: Check document validity (legal status)
            if not self.is_valid(rec, reference_date):
                continue

            # Step 2: Compute time decay weight
            days = self._days_since(rec.fact_date, reference_date)
            weight = self.compute_decay(rec.source, days)

            if weight <= 0:
                continue  # Too old, below minimum weight

            results.append({
                "record": rec,
                "weight": weight,
                "days_ago": days,
            })

        # Sort by weight (most influential first)
        results.sort(key=lambda x: x["weight"], reverse=True)
        return results

    # ──────────────────────────────────────────────────────────────
    # Apply Decay to a List of Scored Signals
    # ──────────────────────────────────────────────────────────────
    def apply_decay_to_scores(
        self,
        scores: List[Dict],
        reference_date: str = None,
    ) -> List[Dict]:
        """
        Apply time decay to a list of signal scores.

        Each score dict must have: {"value": float, "date": str, "source": str}
        Returns the same list with added "decayed_value" and "weight" fields.
        """
        results = []
        for score in scores:
            days = self._days_since(score["date"], reference_date)
            weight = self.compute_decay(score["source"], days)

            if weight <= 0:
                continue

            results.append({
                **score,
                "weight": weight,
                "decayed_value": round(score["value"] * weight, 4),
                "days_ago": days,
            })

        return results

    # ──────────────────────────────────────────────────────────────
    # Weighted Average with Decay
    # ──────────────────────────────────────────────────────────────
    def weighted_average(
        self,
        scores: List[Dict],
        reference_date: str = None,
    ) -> float:
        """
        Compute a time-decay-weighted average of scores.

        Each score dict must have: {"value": float, "date": str, "source": str}
        """
        decayed = self.apply_decay_to_scores(scores, reference_date)
        if not decayed:
            return 0.5  # Neutral baseline when no valid data

        total_weight = sum(d["weight"] for d in decayed)
        if total_weight == 0:
            return 0.5

        weighted_sum = sum(d["value"] * d["weight"] for d in decayed)
        return round(weighted_sum / total_weight, 4)

    # --------------------------------------------------------------
    # Layer-3 verification helpers: trend and sequence reasoning
    # --------------------------------------------------------------
    def detect_multi_signal_change(
        self,
        timeline_points: List[Dict[str, Any]],
        metrics: List[str],
        threshold: float = 0.05,
    ) -> Dict[str, Dict[str, float]]:
        """
        Detect directional change across a timeline for multiple metrics.

        Returns a dict per metric:
            {
                "threat_index": {"baseline": 0.2, "recent": 0.6, "delta": 0.4, "trend": "increasing"},
                ...
            }
        """
        if not timeline_points:
            return {
                metric: {"baseline": 0.0, "recent": 0.0, "delta": 0.0, "trend": "stable"}
                for metric in metrics
            }

        ordered = sorted(timeline_points, key=lambda row: str(row.get("date", "")))
        split = max(1, len(ordered) // 2)
        baseline = ordered[:split]
        recent = ordered[split:] if split < len(ordered) else ordered[-1:]

        result: Dict[str, Dict[str, float]] = {}
        for metric in metrics:
            base_vals = [float(row.get(metric, 0.0) or 0.0) for row in baseline]
            recent_vals = [float(row.get(metric, 0.0) or 0.0) for row in recent]
            base_avg = sum(base_vals) / len(base_vals) if base_vals else 0.0
            recent_avg = sum(recent_vals) / len(recent_vals) if recent_vals else 0.0
            delta = recent_avg - base_avg
            if delta > threshold:
                trend = "increasing"
            elif delta < -threshold:
                trend = "decreasing"
            else:
                trend = "stable"
            result[metric] = {
                "baseline": round(base_avg, 4),
                "recent": round(recent_avg, 4),
                "delta": round(delta, 4),
                "trend": trend,
            }

        return result

    def validate_event_sequence(
        self,
        observations: List[Any],
        expected_sequence: List[Any],
        actor_pair: Optional[Tuple[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Validate whether observations follow an expected ordered sequence.

        `observations` are ObservationRecords; `expected_sequence` can contain
        ActionType values or raw action strings.
        """
        if not observations or not expected_sequence:
            return {
                "matched": False,
                "matched_actions": [],
                "missing_actions": [str(x) for x in expected_sequence],
                "matched_observation_ids": [],
            }

        normalized_expected = []
        for item in expected_sequence:
            if hasattr(item, "value"):
                normalized_expected.append(str(item.value))
            else:
                normalized_expected.append(str(item))

        filtered = observations
        if actor_pair:
            pair = {actor_pair[0].upper(), actor_pair[1].upper()}
            filtered = [
                obs for obs in observations
                if pair.issubset({a.upper() for a in getattr(obs, "actors", [])})
            ]

        ordered = sorted(filtered, key=lambda obs: str(getattr(obs, "event_date", "")))
        matched_actions: List[str] = []
        matched_ids: List[str] = []
        cursor = 0
        for obs in ordered:
            if cursor >= len(normalized_expected):
                break
            action_value = getattr(getattr(obs, "action_type", None), "value", None)
            if action_value is None:
                action_value = str(getattr(obs, "action_type", ""))
            action_value = str(action_value)
            if action_value == normalized_expected[cursor]:
                matched_actions.append(action_value)
                matched_ids.append(str(getattr(obs, "obs_id", "")))
                cursor += 1

        missing = normalized_expected[cursor:]
        return {
            "matched": cursor == len(normalized_expected),
            "matched_actions": matched_actions,
            "missing_actions": missing,
            "matched_observation_ids": matched_ids,
        }

    # ──────────────────────────────────────────────────────────────
    # Get Rules Summary (for transparency)
    # ──────────────────────────────────────────────────────────────
    def get_rules_summary(self) -> List[Dict]:
        """Return human-readable summary of all decay rules."""
        summary = []
        for name, rule in self.rules.items():
            summary.append({
                "source": name,
                "half_life_days": rule.half_life_days,
                "max_age_days": rule.max_age_days,
                "min_weight": rule.min_weight,
                "description": rule.description,
                "example_7d": round(self.compute_decay(name, 7), 3),
                "example_30d": round(self.compute_decay(name, 30), 3),
                "example_365d": round(self.compute_decay(name, 365), 3),
            })
        return summary


# ══════════════════════════════════════════════════════════════════
# Singleton
# ══════════════════════════════════════════════════════════════════
temporal_reasoner = TemporalReasoner()
