"""
Belief Accumulator — converts observations into beliefs through corroboration.

Epistemic chain:
    Evidence (raw text)  →  Observation ("I think I saw X")  →  Belief ("X is happening")

An observation alone is NOT evidence.  A blog post mentioning "troops"
should not immediately alter a geopolitical assessment.

A belief requires **independent corroboration**:
    - Multiple OSINT sources with different origin_ids
    - OSINT + dataset agreement
    - A single high-reliability source (GOV, SENSOR, DATASET)

This prevents the Iraq WMD problem: multiple reports citing the same
original source being treated as independent confirmation.

Algorithm:
    1. Group observations by signal code
    2. Deduplicate by origin_id (echo reporting → 1 observation)
    3. Compute support_score per signal
    4. Promote to belief only if support_score > threshold

Usage
-----
    from engine.Layer3_StateModel.belief_accumulator import BeliefAccumulator

    acc = BeliefAccumulator()
    beliefs = acc.evaluate(observations)
    # beliefs is a list of dicts ready for state model update

Wired into:
    state_provider.investigate_and_update()
    (between signal_hits extraction and state model update)
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Layer3.belief_accumulator")


# =====================================================================
# Source reliability tiers (must match evidence_assimilator)
# =====================================================================

SOURCE_RELIABILITY: Dict[str, float] = {
    "SOCIAL":      0.30,
    "OSINT":       0.55,
    "MOLTBOT":     0.55,
    "NEWS":        0.55,
    "GOV":         0.75,
    "UN":          0.80,
    "SIPRI":       0.85,
    "SENSOR":      0.90,
    "ANALYST":     0.90,
    "DATASET":     0.90,
}

# =====================================================================
# Belief promotion thresholds
# =====================================================================

BELIEF_THRESHOLDS: Dict[str, Tuple[float, float]] = {
    # (min_support, max_support) for each belief level
    "ignore":   (0.00, 0.35),
    "weak":     (0.35, 0.55),
    "moderate": (0.55, 0.75),
    "strong":   (0.75, 1.00),
}

# Minimum support_score to promote observation → belief
PROMOTION_THRESHOLD = 0.35

# Recency half-life in hours — military signals decay fast
RECENCY_HALF_LIFE_HOURS = 72.0

# Staleness threshold — articles older than this are severely discounted
STALENESS_THRESHOLD_DAYS = 30

# Source diversity bonus — reward multi-sensor agreement
# (e.g. GDELT + MoltBot both detect SIG_MIL_ESCALATION)
SOURCE_DIVERSITY_BONUS = 0.10
SOURCE_DIVERSITY_CAP   = 0.20


# =====================================================================
# Belief Accumulator
# =====================================================================

class BeliefAccumulator:
    """
    Converts observations into beliefs through evidence accumulation.

    Call ``evaluate(observations)`` with a list of observation dicts
    (from ``extract_observations`` or ``extract_observations_batch``).

    Returns a list of belief dicts, each representing a signal that
    has enough independent corroboration to be treated as real.
    """

    def __init__(
        self,
        promotion_threshold: float = PROMOTION_THRESHOLD,
        recency_half_life_hours: float = RECENCY_HALF_LIFE_HOURS,
        now: Optional[datetime] = None,
    ):
        self.promotion_threshold = promotion_threshold
        self.recency_half_life_hours = recency_half_life_hours
        self.now = now or datetime.now(timezone.utc).replace(tzinfo=None)

    # ─────────────────────────────────────────────────────────────────
    # Main entry point
    # ─────────────────────────────────────────────────────────────────

    def evaluate(
        self, observations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate a set of observations and return promoted beliefs.

        Steps:
            1. Group by signal code
            2. Deduplicate by origin_id (echo reporting collapses to 1)
            3. Compute support_score per signal
            4. Promote to belief if support_score >= threshold

        Returns
        -------
        list[dict]
            Each belief dict has:
                signal          — canonical signal code
                support_score   — accumulated evidence weight
                belief_level    — "weak" | "moderate" | "strong"
                confidence      — same as support_score (state model compat)
                recency         — freshness of newest observation (0–1)
                corroboration   — number of independent observations
                sources         — list of contributing source types
                observations    — the deduplicated observations that formed this
        """
        if not observations:
            return []

        # 1. Group by signal
        #    Phase 8: Canonicalize signal names using the unified signal
        #    registry so that economic variants (SIG_ECON_PRESSURE,
        #    SIG_ECONOMIC_PRESSURE, SIG_ECO_PRESSURE_HIGH) merge into one
        #    strong belief instead of N separate weak beliefs.
        try:
            from engine.Layer3_StateModel.signal_registry import canonicalize as _canonicalize
        except ImportError:
            def _canonicalize(t: str) -> str:
                return t

        by_signal: Dict[str, List[Dict[str, Any]]] = {}
        for obs in observations:
            if obs.get("type") != "observation":
                continue
            signal = obs.get("signal", "")
            if not signal:
                continue
            # Canonicalize via unified registry
            signal = _canonicalize(signal)
            by_signal.setdefault(signal, []).append(obs)

        # 2–4. Process each signal group
        beliefs: List[Dict[str, Any]] = []
        rejected: List[str] = []

        for signal, obs_list in by_signal.items():
            belief = self._accumulate(signal, obs_list)
            if belief is not None:
                beliefs.append(belief)
            else:
                rejected.append(signal)

        if beliefs:
            logger.info(
                "Belief accumulator: %d signal(s) → %d belief(s) promoted, "
                "%d rejected (insufficient evidence)",
                len(by_signal), len(beliefs), len(rejected),
            )
        if rejected:
            logger.debug(
                "Rejected signals (below threshold %.2f): %s",
                self.promotion_threshold, rejected,
            )

        return beliefs

    # ─────────────────────────────────────────────────────────────────
    # Per-signal accumulation
    # ─────────────────────────────────────────────────────────────────

    def _accumulate(
        self, signal: str, obs_list: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Accumulate evidence for a single signal and decide promotion.

        Enhancements over the basic version:
        - **Date-confidence weighting**: crawl-time observations are
          discounted by their ``date_confidence`` (default 0.30).
        - **Staleness guard**: articles > 30 days old get steep decay.
        - **Source diversity bonus**: multi-sensor agreement (e.g.
          GDELT + MoltBot) gets a corroboration bonus.
        - **Verification status**: each belief is tagged as
          "confirmed", "corroborated", "single-source", or "unverified".

        Returns a belief dict if promoted, None if rejected.
        """
        # 2. Deduplicate by origin_id — echo reporting → 1 observation
        unique: Dict[str, Dict[str, Any]] = {}
        for obs in obs_list:
            oid = obs.get("origin_id", "")
            if not oid:
                # No origin_id → treat as unique (legacy compat)
                oid = f"_noid_{id(obs)}"
            if oid not in unique:
                unique[oid] = obs
            else:
                # Keep the stronger observation for this origin
                if obs.get("evidence_strength", 0) > unique[oid].get("evidence_strength", 0):
                    unique[oid] = obs

        deduplicated = list(unique.values())
        echo_count = len(obs_list) - len(deduplicated)
        if echo_count > 0:
            logger.debug(
                "%s: collapsed %d echo observations → %d unique",
                signal, len(obs_list), len(deduplicated),
            )

        # 3. Compute support_score
        #    support = Σ (evidence_strength × source_reliability × recency_weight × date_confidence)
        support_score = 0.0
        newest_ts = ""
        newest_dt: Optional[datetime] = None
        all_sources: List[str] = []
        source_origins: set = set()          # unique source types for diversity
        publisher_origins: set = set()       # unique publishers for independence

        for obs in deduplicated:
            strength = float(obs.get("evidence_strength", 0.0))
            source_type = str(obs.get("source_type", obs.get("source", "OSINT"))).upper()
            reliability = SOURCE_RELIABILITY.get(source_type, 0.40)
            recency_weight = self._recency_weight(
                obs.get("timestamp", ""),
                date_source=obs.get("date_source", ""),
                source_type=source_type,
            )

            # ── Date-confidence discount ─────────────────────────
            # Observations with crawl-time (no real date) are
            # discounted: their temporal signal is unreliable.
            # Phase 8: floor raised 0.30 → 0.50 to reduce compound
            # discount on typical OSINT with no explicit date.
            date_conf = float(obs.get("date_confidence", 1.0))
            if date_conf <= 0:
                date_conf = 0.50  # floor — Phase 8 raised from 0.30

            # ── Staleness guard ──────────────────────────────────
            # Articles > STALENESS_THRESHOLD_DAYS old get a severe
            # additional penalty on top of normal recency decay.
            staleness_factor = self._staleness_factor(
                obs.get("timestamp", ""),
                date_source=obs.get("date_source", ""),
                source_type=source_type,
            )

            # ── Event confidence ─────────────────────────────────
            # Commentary / analysis articles get low event_confidence,
            # so "Explainer: Iran nuclear program" won't inflate SRE.
            # Phase 8: floor raised 0.20 → 0.40 and switched from
            # multiplicative to geometric-mean for the confidence pair
            # to reduce the 94% compound discount.
            event_conf = float(obs.get("event_confidence", 1.0))
            if event_conf <= 0:
                event_conf = 0.40  # floor — Phase 8 raised from 0.20

            # Phase 8: geometric mean of date_conf × event_conf
            # replaces raw product to avoid compound discount.
            # Old: 0.30 × 0.20 = 0.06  |  New: sqrt(0.50 × 0.40) = 0.447
            _conf_factor = math.sqrt(date_conf * event_conf)

            contribution = (
                strength * reliability * recency_weight
                * _conf_factor * staleness_factor
            )
            support_score += contribution

            # Track publisher domain for independence check
            publisher = str(obs.get("publisher_domain", ""))
            if publisher:
                publisher_origins.add(publisher)

            source_origins.add(source_type)
            all_sources.append(source_type)

            obs_ts = self._authoritative_timestamp(obs)
            obs_dt = self._parse_timestamp(obs_ts)
            if obs_dt and (newest_dt is None or obs_dt > newest_dt):
                newest_dt = obs_dt
                newest_ts = obs_ts

        # ── Source diversity bonus ───────────────────────────────
        # When multiple INDEPENDENT sensor types agree on the same
        # signal, apply a bonus (e.g. GDELT + MOLTBOT = +0.10).
        n_unique_sources = len(source_origins)
        diversity_bonus = 0.0
        if n_unique_sources >= 2:
            diversity_bonus = min(
                SOURCE_DIVERSITY_CAP,
                SOURCE_DIVERSITY_BONUS * (n_unique_sources - 1),
            )
            support_score += diversity_bonus
            logger.debug(
                "%s: source diversity bonus +%.2f (%d sensor types: %s)",
                signal, diversity_bonus, n_unique_sources, sorted(source_origins),
            )

        # ── Publisher independence check ─────────────────────
        # Reuters -> TimesNow -> News18 -> RepublicWorld = 1 source,
        # NOT 4.  We count unique canonical publishers to prevent
        # syndication loops from inflating corroboration.
        n_unique_publishers = len(publisher_origins) if publisher_origins else n_unique_sources

        # Phase 8: Publisher diversity bonus — when 3+ distinct
        # publishers report the same signal, grant partial bonus
        # even if they share a source_type (e.g. all NEWS).
        if n_unique_publishers >= 3 and diversity_bonus == 0.0:
            publisher_bonus = min(
                SOURCE_DIVERSITY_CAP / 2,
                0.05 * (n_unique_publishers - 2),
            )
            support_score += publisher_bonus
            logger.debug(
                "%s: publisher diversity bonus +%.2f (%d publishers: %s)",
                signal, publisher_bonus, n_unique_publishers,
                sorted(publisher_origins),
            )

        # Cap at 0.95 — never perfectly certain from OSINT alone
        support_score = min(support_score, 0.95)

        # 4. Promotion decision
        if support_score < self.promotion_threshold:
            return None

        # Determine belief level
        belief_level = "weak"
        for level, (lo, hi) in BELIEF_THRESHOLDS.items():
            if level == "ignore":
                continue
            if lo <= support_score < hi:
                belief_level = level
                break
        if support_score >= 0.75:
            belief_level = "strong"

        # ── Verification status ──────────────────────────────────
        # Use PUBLISHER count (not raw observation count) to prevent
        # syndication echo-chambers from inflating verification.
        n_indep = len(deduplicated)
        if n_unique_publishers >= 3 and n_unique_sources >= 2:
            verification_status = "confirmed"
        elif n_unique_publishers >= 2:
            verification_status = "corroborated"
        elif n_indep == 1:
            verification_status = "single-source"
        else:
            verification_status = "unverified"

        # Compute recency from newest observation timestamp
        recency = self._recency_weight(
            newest_ts,
            date_source="authoritative" if newest_ts else "unknown",
            source_type="DATASET" if newest_ts else "",
        )

        belief = {
            "signal":              signal,
            "support_score":       round(support_score, 4),
            "belief_level":        belief_level,
            "confidence":          round(support_score, 4),
            "recency":             round(recency, 4),
            "corroboration":       n_indep,
            "echo_collapsed":      echo_count,
            "sources":             sorted(set(all_sources)),
            "source_count":        n_unique_sources,
            "independent_sources": sorted(source_origins),
            "unique_publishers":   n_unique_publishers,
            "publisher_domains":   sorted(publisher_origins),
            "diversity_bonus":     round(diversity_bonus, 4),
            "verification_status": verification_status,
            "observations":        deduplicated,
        }

        logger.info(
            "BELIEF PROMOTED: %s  support=%.3f  level=%s  "
            "corroboration=%d  publishers=%d  sources=%s  recency=%.2f  "
            "verification=%s  diversity_bonus=%.2f",
            signal, support_score, belief_level,
            n_indep, n_unique_publishers, sorted(set(all_sources)), recency,
            verification_status, diversity_bonus,
        )

        # ── Date-source drift monitoring ──────────────────────────
        # Track how many observations use real publish dates vs crawl-time.
        _real = sum(
            1 for o in deduplicated
            if o.get("date_source", "crawl_time") != "crawl_time"
        )
        _crawl = len(deduplicated) - _real
        if _crawl > 0:
            logger.info(
                "[TEMPORAL-AUDIT] %s: %d/%d observations use real publish dates "
                "(%d still crawl-time, date_confidence discount applied)",
                signal, _real, len(deduplicated), _crawl,
            )

        return belief

    # ─────────────────────────────────────────────────────────────────
    # Recency decay
    # ─────────────────────────────────────────────────────────────────

    def _recency_weight(
        self,
        timestamp_str: str,
        *,
        date_source: str = "",
        source_type: str = "",
    ) -> float:
        """
        Compute recency weight using exponential decay.

            recency = exp(-age_hours / half_life)

        72-hour half-life: a 3-day-old observation has weight 0.50.
        A fresh observation has weight ~1.0.
        A 1-week-old observation has weight ~0.13.

        Unknown or crawl-time-only dates are heavily discounted.
        """
        if not self._has_authoritative_time(timestamp_str, date_source=date_source, source_type=source_type):
            return 0.20

        obs_time = self._parse_timestamp(timestamp_str)
        if obs_time is None:
            return 0.15

        age_hours = max(0.0, (self.now - obs_time).total_seconds() / 3600.0)
        decay = math.exp(-age_hours / self.recency_half_life_hours)
        return max(0.01, min(1.0, decay))

    # ─────────────────────────────────────────────────────────────────
    # Staleness guard
    # ─────────────────────────────────────────────────────────────────

    def _staleness_factor(
        self,
        timestamp_str: str,
        *,
        date_source: str = "",
        source_type: str = "",
    ) -> float:
        """
        Apply steep penalty for articles older than STALENESS_THRESHOLD_DAYS.

        - Fresh articles (< threshold): factor = 1.0 (no penalty)
        - Old articles (> threshold): factor decays linearly from 1.0 → 0.1

        This prevents resurfaced old articles from faking escalation spikes.
        """
        if not self._has_authoritative_time(timestamp_str, date_source=date_source, source_type=source_type):
            return 0.50

        obs_time = self._parse_timestamp(timestamp_str)
        if obs_time is None:
            return 0.50

        age_days = max(0.0, (self.now - obs_time).total_seconds() / 86400.0)

        if age_days <= STALENESS_THRESHOLD_DAYS:
            return 1.0

        # Linear decay from 1.0 → 0.10 between threshold and 2× threshold
        overage = (age_days - STALENESS_THRESHOLD_DAYS) / STALENESS_THRESHOLD_DAYS
        factor = max(0.10, 1.0 - overage * 0.90)

        if factor < 0.50:
            logger.info(
                "[TEMPORAL-AUDIT] Stale article (%.0f days old): "
                "staleness_factor=%.2f", age_days, factor,
            )
        return factor


    @staticmethod
    def _has_authoritative_time(timestamp_str: Any, *, date_source: str = "", source_type: str = "") -> bool:
        if not str(timestamp_str or "").strip():
            return False
        date_tag = str(date_source or "").strip().lower()
        src = str(source_type or "").strip().upper()
        if date_tag in {"crawl_time", "unknown", "crawl"}:
            return False
        if not date_tag:
            return src in {"DATASET", "SENSOR", "GOV", "UN", "SIPRI"}
        return True

    @staticmethod
    def _parse_timestamp(timestamp_str: Any) -> Optional[datetime]:
        token = str(timestamp_str or "").strip()
        if not token:
            return None
        try:
            obs_time = datetime.fromisoformat(token.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            try:
                obs_time = datetime.fromisoformat(token[:19])
            except (ValueError, TypeError):
                return None
        if getattr(obs_time, "tzinfo", None) is not None:
            obs_time = obs_time.replace(tzinfo=None)
        return obs_time

    def _authoritative_timestamp(self, observation: Dict[str, Any]) -> str:
        ts = str(observation.get("timestamp", "") or "").strip()
        if not self._has_authoritative_time(
            ts,
            date_source=observation.get("date_source", ""),
            source_type=observation.get("source_type", observation.get("source", "")),
        ):
            return ""
        return ts


# =====================================================================
# Convenience: apply beliefs to state context
# =====================================================================

def apply_beliefs_to_state(
    state_context: Any,
    beliefs: List[Dict[str, Any]],
) -> List[str]:
    """
    Apply promoted beliefs to a StateContext, updating signal_confidence
    and observed_signals.

    Only beliefs that IMPROVE existing confidence are applied
    (never downgrades from a dataset reading).

    Parameters
    ----------
    state_context : StateContext
        The state context to update in place.
    beliefs : list[dict]
        Output from ``BeliefAccumulator.evaluate()``.

    Returns
    -------
    list[str]
        Signal codes that were actually updated (new or improved).
    """
    updated: List[str] = []

    signal_confidence = getattr(state_context, "signal_confidence", {})
    if signal_confidence is None:
        signal_confidence = {}
    observed_signals = getattr(state_context, "observed_signals", set())
    if observed_signals is None:
        observed_signals = set()

    for belief in beliefs:
        signal = belief["signal"]
        new_conf = belief["confidence"]
        new_recency = belief["recency"]

        existing_conf = float(signal_confidence.get(signal, 0.0) or 0.0)

        # Only upgrade — NEVER downgrade a dataset/sensor reading
        if new_conf > existing_conf:
            signal_confidence[signal] = new_conf
            updated.append(signal)

            # Mark as observed if confidence is meaningful
            if new_conf >= 0.35:
                observed_signals.add(signal)

            logger.info(
                "Belief applied: %s  confidence %.3f → %.3f  "
                "level=%s  corroboration=%d",
                signal, existing_conf, new_conf,
                belief["belief_level"], belief["corroboration"],
            )
        else:
            logger.debug(
                "Belief skipped: %s  existing=%.3f >= new=%.3f",
                signal, existing_conf, new_conf,
            )

    # Write back
    state_context.signal_confidence = signal_confidence
    state_context.observed_signals = observed_signals

    if updated:
        logger.info(
            "Belief accumulator updated %d signal(s): %s",
            len(updated), updated,
        )

    # ── Record temporal snapshot ─────────────────────────────────
    # After beliefs are committed to state, snapshot the current
    # signal_confidence for trend analysis.
    try:
        from engine.Layer3_StateModel.temporal_memory import record_beliefs
        snapshot = {k: float(v) for k, v in signal_confidence.items() if float(v) > 0}
        if snapshot:
            record_beliefs(snapshot)
    except Exception as e:
        logger.debug("Temporal snapshot skipped: %s", e)

    return updated


__all__ = [
    "BeliefAccumulator",
    "apply_beliefs_to_state",
    "BELIEF_THRESHOLDS",
    "PROMOTION_THRESHOLD",
    "SOURCE_RELIABILITY",
]
