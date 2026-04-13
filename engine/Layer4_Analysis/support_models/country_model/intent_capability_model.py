"""
Intent vs Capability Model — The Dual-Channel Analyzer
=========================================================
The most consequential analytical distinction in geopolitics:

    INTENT:      what a country WANTS to do
    CAPABILITY:  what a country CAN do

These are completely different signals:
    - High intent + high capability = DANGER (real escalation risk)
    - High intent + low capability = BLUFF (threats without means)
    - Low intent + high capability = DETERRENCE (quiet power)
    - Low intent + low capability = NON-FACTOR

Without this separation:
    Your AI cannot distinguish between a nuclear power that issues
    a polite protest (low intent, high capability = deterrence)
    and a militia leader who screams on TV about war
    (high intent, low capability = bluff).

    And that difference is literally the difference between
    WW3 and a news cycle.

Design:
    - Observations are classified as intent signals or capability signals
    - computed separate scores for each channel
    - country_state_builder uses both, NOT a blended score
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Set, Optional, Tuple
from enum import Enum
from datetime import datetime
import logging
import sys
import os
from pathlib import Path

# Keep module importable after package relocation.
_here = Path(__file__).resolve()
_root = None
for parent in _here.parents:
    if (parent / "contracts").exists():
        _root = parent
        break
if _root is None:
    _root = _here.parents[3]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from contracts.observation import ObservationRecord, ActionType, SourceType

logger = logging.getLogger("intent_capability_model")


# =====================================================================
# Signal Channel Classification
# =====================================================================

class SignalChannel(Enum):
    """Which analytical channel an observation feeds."""
    INTENT     = "intent"       # What they say, threaten, promise
    CAPABILITY = "capability"   # What they have, build, deploy
    BOTH       = "both"         # Some observations carry both signals
    NEITHER    = "neither"      # Neutral state (economic indicators)


# Map ActionType → SignalChannel
ACTION_CHANNEL: Dict[ActionType, SignalChannel] = {
    # INTENT signals — words, diplomacy, rhetoric
    ActionType.STATEMENT:          SignalChannel.INTENT,
    ActionType.DIPLOMACY:          SignalChannel.INTENT,
    ActionType.CONSULTATION:       SignalChannel.INTENT,
    ActionType.THREATEN_MILITARY:  SignalChannel.INTENT,
    ActionType.COOPERATION:        SignalChannel.INTENT,
    ActionType.AID:                SignalChannel.INTENT,    # Promise of aid = intent
    ActionType.EXPULSION:          SignalChannel.INTENT,

    # CAPABILITY signals — material, economic, military
    ActionType.MOBILIZE:           SignalChannel.CAPABILITY,  # Actual troop movement
    ActionType.BLOCKADE:           SignalChannel.CAPABILITY,  # Physical action
    ActionType.CYBER_ATTACK:       SignalChannel.CAPABILITY,  # Technical capability
    ActionType.ARMS_TRANSFER:      SignalChannel.CAPABILITY,  # Military hardware
    ActionType.TRADE_FLOW:         SignalChannel.CAPABILITY,  # Economic capacity
    ActionType.ECONOMIC_INDICATOR: SignalChannel.CAPABILITY,  # Structural capacity

    # BOTH — these carry intent AND capability signals
    ActionType.SANCTION:           SignalChannel.BOTH,    # Intent to punish + capacity to do it
    ActionType.TRADE_RESTRICTION:  SignalChannel.BOTH,    # Intent + economic leverage
    ActionType.VIOLENCE:           SignalChannel.BOTH,    # Will to fight + ability
    ActionType.WAR:                SignalChannel.BOTH,    # Maximum both
    ActionType.PRESSURE:           SignalChannel.BOTH,    # Coercive intent + some capability

    # NEITHER — internal, neutral
    ActionType.OBSERVATION:        SignalChannel.NEITHER,
    ActionType.ELECTION:           SignalChannel.NEITHER,
    ActionType.POLICY_CHANGE:      SignalChannel.NEITHER,
    ActionType.PROTEST:            SignalChannel.NEITHER,
    ActionType.COUP_ATTEMPT:       SignalChannel.BOTH,    # Internal but intent+capability
    ActionType.TRADE_AGREEMENT:    SignalChannel.INTENT,  # Document = intent
}

# Source types that are stronger indicators of capability vs intent
CAPABILITY_SOURCES: Set[str] = {
    "sipri", "world_bank", "un_comtrade", "imf",
    "census", "correlates_of_war",
}

INTENT_SOURCES: Set[str] = {
    "news_reuters", "news_ap", "news_bbc", "news_generic",
    "news_state_media", "govt_statements", "social_media",
    "scraped_statement", "moltbot_scrape",
}


def classify_channel(obs: ObservationRecord) -> SignalChannel:
    """Classify an observation into intent or capability channel."""
    # Primary classification by action type
    channel = ACTION_CHANNEL.get(obs.action_type, SignalChannel.NEITHER)

    # Secondary refinement by source type
    # If the source is fundamentally a capability database, upgrade
    if obs.source.lower() in CAPABILITY_SOURCES and channel == SignalChannel.NEITHER:
        channel = SignalChannel.CAPABILITY

    if obs.source.lower() in INTENT_SOURCES and channel == SignalChannel.NEITHER:
        channel = SignalChannel.INTENT

    return channel


# =====================================================================
# Intent-Capability Profile
# =====================================================================

@dataclass
class IntentCapabilityProfile:
    """
    Dual-channel assessment for a country.

    This replaces blended scores with separated channels:
        intent_score:     0.0 (peaceful) to 1.0 (aggressive intent)
        capability_score: 0.0 (no capacity) to 1.0 (full capacity)

    The COMBINATION matters:
        high/high → real danger
        high/low  → bluff
        low/high  → deterrence
        low/low   → non-factor
    """
    country: str
    date: str = ""

    # Scores
    intent_score: float = 0.5         # Default neutral
    capability_score: float = 0.5     # Default unknown
    raw_intent_score: float = 0.5     # Intent before legal-legitimacy adjustment
    action_readiness: float = 0.5     # Intent + capability + legitimacy

    # Classification
    posture: str = "unknown"          # "danger", "bluff", "deterrence", "non-factor", "unknown"

    # Supporting data
    intent_observations: int = 0
    capability_observations: int = 0
    intent_sources: List[str] = field(default_factory=list)
    capability_sources: List[str] = field(default_factory=list)
    legal_signal_count: int = 0
    legal_confidence: float = 0.0
    legitimacy_score: float = 0.5
    legitimacy_context: str = "unknown"

    # Cooperative vs hostile breakdown within intent
    cooperative_intent: float = 0.0
    hostile_intent: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "country": self.country,
            "date": self.date,
            "intent_score": round(self.intent_score, 4),
            "raw_intent_score": round(self.raw_intent_score, 4),
            "capability_score": round(self.capability_score, 4),
            "action_readiness": round(self.action_readiness, 4),
            "posture": self.posture,
            "intent_observations": self.intent_observations,
            "capability_observations": self.capability_observations,
            "intent_sources": self.intent_sources,
            "capability_sources": self.capability_sources,
            "legal_signal_count": self.legal_signal_count,
            "legal_confidence": round(self.legal_confidence, 4),
            "legitimacy_score": round(self.legitimacy_score, 4),
            "legitimacy_context": self.legitimacy_context,
            "cooperative_intent": round(self.cooperative_intent, 4),
            "hostile_intent": round(self.hostile_intent, 4),
        }


# =====================================================================
# Posture classification thresholds
# =====================================================================

INTENT_HIGH_THRESHOLD = 0.60
INTENT_LOW_THRESHOLD = 0.40
CAPABILITY_HIGH_THRESHOLD = 0.60
CAPABILITY_LOW_THRESHOLD = 0.40


def classify_posture(intent: float, capability: float) -> str:
    """
    Classify the strategic posture from intent and capability scores.

    Returns:
        "danger"     — high intent + high capability
        "bluff"      — high intent + low capability
        "deterrence" — low intent + high capability
        "non_factor" — low intent + low capability
        "ambiguous"  — scores are in the middle ranges
    """
    high_i = intent >= INTENT_HIGH_THRESHOLD
    low_i = intent <= INTENT_LOW_THRESHOLD
    high_c = capability >= CAPABILITY_HIGH_THRESHOLD
    low_c = capability <= CAPABILITY_LOW_THRESHOLD

    if high_i and high_c:
        return "danger"
    elif high_i and low_c:
        return "bluff"
    elif low_i and high_c:
        return "deterrence"
    elif low_i and low_c:
        return "non_factor"
    else:
        return "ambiguous"


# =====================================================================
# Intent-Capability Model
# =====================================================================

class IntentCapabilityModel:
    """
    Separates observations into intent and capability channels
    and produces a dual-score profile.

    Usage:
        model = IntentCapabilityModel()
        profile = model.analyze(country="RUS", observations=obs_list)

        if profile.posture == "danger":
            print("HIGH ALERT: Both intent and capability are elevated")
        elif profile.posture == "bluff":
            print("Threats detected but limited capability to execute")
    """

    def analyze(
        self,
        country: str,
        observations: List[ObservationRecord],
        date: str = None,
        legal_signal_pack: Optional[Dict[str, Any]] = None,
    ) -> IntentCapabilityProfile:
        """
        Analyze observations for a country and produce intent/capability profile.

        Args:
            country: Country code (ISO3)
            observations: Observations involving this country
            date: Analysis date

        Returns:
            IntentCapabilityProfile with separated scores
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Filter observations for this country. We only treat signals as
        # "owned" by the country when it is the directional source actor.
        # This avoids the classic bug where A->B threats inflate B's intent.
        country_obs = [
            obs for obs in observations
            if self._is_source_actor(obs, country)
        ]

        if not country_obs:
            return IntentCapabilityProfile(country=country, date=date)

        # Separate into channels
        intent_obs: List[ObservationRecord] = []
        capability_obs: List[ObservationRecord] = []

        for obs in country_obs:
            channel = classify_channel(obs)
            if channel == SignalChannel.INTENT:
                intent_obs.append(obs)
            elif channel == SignalChannel.CAPABILITY:
                capability_obs.append(obs)
            elif channel == SignalChannel.BOTH:
                intent_obs.append(obs)
                capability_obs.append(obs)
            # NEITHER → skip

        # Compute intent score
        intent_score, coop, hostile = self._compute_intent(intent_obs)
        raw_intent = intent_score

        # Compute capability score
        capability_score = self._compute_capability(capability_obs)

        # Compute legal-legitimacy context (separate channel from intent/capability).
        legitimacy_score, legitimacy_context, legal_count, legal_conf = self._compute_legitimacy(
            legal_signal_pack
        )
        intent_score = self._apply_legitimacy_adjustment(intent_score, legitimacy_score, legal_count)
        action_readiness = self._compute_action_readiness(
            intent=intent_score,
            capability=capability_score,
            legitimacy=legitimacy_score,
        )

        # Classify posture
        posture = classify_posture(intent_score, capability_score)

        return IntentCapabilityProfile(
            country=country,
            date=date,
            intent_score=round(intent_score, 4),
            capability_score=round(capability_score, 4),
            raw_intent_score=round(raw_intent, 4),
            action_readiness=round(action_readiness, 4),
            posture=posture,
            intent_observations=len(intent_obs),
            capability_observations=len(capability_obs),
            intent_sources=sorted(set(o.source for o in intent_obs)),
            capability_sources=sorted(set(o.source for o in capability_obs)),
            legal_signal_count=legal_count,
            legal_confidence=round(legal_conf, 4),
            legitimacy_score=round(legitimacy_score, 4),
            legitimacy_context=legitimacy_context,
            cooperative_intent=round(coop, 4),
            hostile_intent=round(hostile, 4),
        )

    def _is_source_actor(self, obs: ObservationRecord, country: str) -> bool:
        """
        Return True when `country` is the action initiator for `obs`.

        Priority:
        1) Explicit directional field (`AAA -> BBB`)
        2) Fallback to Actor1 convention (`actors[0]`)
        """
        target = country.upper()
        direction = (obs.direction or "").strip()
        if "->" in direction:
            src = direction.split("->", 1)[0].strip().upper()
            return src == target

        if obs.actors:
            return (obs.actors[0] or "").upper() == target

        return False

    def _compute_intent(
        self, intent_obs: List[ObservationRecord]
    ) -> tuple:
        """
        Compute intent score from intent-channel observations.

        Hostile actions increase intent score.
        Cooperative actions decrease it.
        Weighted by intensity and confidence.

        Returns:
            (overall_intent, cooperative_component, hostile_component)
        """
        if not intent_obs:
            return 0.5, 0.0, 0.0  # Neutral default

        cooperative_weight = 0.0
        hostile_weight = 0.0
        total_weight = 0.0

        # Import the direction classifier from contradiction engine
        from engine.Layer3_StateModel.validation.contradiction_engine import (
            get_signal_direction, SignalDirection,
        )

        for obs in intent_obs:
            direction = get_signal_direction(obs.action_type)
            weight = obs.intensity * obs.confidence

            if direction == SignalDirection.COOPERATIVE:
                cooperative_weight += weight
            elif direction == SignalDirection.HOSTILE:
                hostile_weight += weight

            total_weight += weight

        if total_weight == 0:
            return 0.5, 0.0, 0.0

        # Intent polarity: 0.0 = purely cooperative, 1.0 = purely hostile
        cooperative_frac = cooperative_weight / total_weight
        hostile_frac = hostile_weight / total_weight

        # Map polarity to 0-1 and temper with evidence volume so a single
        # hostile statement does not look equivalent to a sustained campaign.
        polarity = (hostile_frac - cooperative_frac + 1.0) / 2.0
        evidence_strength = min(1.0, total_weight / 3.0)
        intent = 0.5 + (polarity - 0.5) * evidence_strength
        intent = max(0.0, min(1.0, intent))

        return intent, cooperative_frac, hostile_frac

    def _compute_capability(
        self, capability_obs: List[ObservationRecord]
    ) -> float:
        """
        Compute capability score from capability-channel observations.

        Higher intensity observations from capability sources → higher capability.
        """
        if not capability_obs:
            return 0.5  # Unknown = neutral

        weighted_sum = 0.0
        weight_total = 0.0

        for obs in capability_obs:
            # Weight by confidence (more reliable sources count more)
            w = obs.confidence
            weighted_sum += obs.intensity * w
            weight_total += w

        if weight_total == 0:
            return 0.5

        return weighted_sum / weight_total

    def _compute_legitimacy(
        self,
        legal_signal_pack: Optional[Dict[str, Any]],
    ) -> Tuple[float, str, int, float]:
        """
        Derive a legal-legitimacy channel from extracted legal signals.

        - High score: stronger legal basis for state action.
        - Low score: strong constraints/prohibitions/rights barriers.
        """
        if not legal_signal_pack:
            return 0.5, "unknown", 0, 0.0

        signals = legal_signal_pack.get("signals", [])
        if not isinstance(signals, list) or not signals:
            return 0.5, "unknown", 0, 0.0

        pro_action = 0.0
        constraints = 0.0
        confidences: List[float] = []

        for signal in signals:
            if not isinstance(signal, dict):
                continue
            modality = str(signal.get("modality", "may")).lower()
            actor = str(signal.get("actor", "unknown")).lower()
            provision_type = str(signal.get("provision_type", "duty")).lower()
            overrides = signal.get("overrides", []) or []
            interpretive_terms = signal.get("interpretive_terms", []) or []

            strength = float(signal.get("strength", 0.5) or 0.5)
            uncertainty_penalty = min(0.25, len(interpretive_terms) * 0.04)
            confidence = max(0.1, min(1.0, strength - uncertainty_penalty))
            confidences.append(confidence)

            is_state_actor = actor in {"state", "authority", "government", "executive"}
            if modality == "prohibited" or provision_type == "right":
                constraints += confidence * (1.2 if modality == "prohibited" else 1.0)

            if is_state_actor:
                if modality in {"may", "shall", "must"} and provision_type in {
                    "power",
                    "exception",
                    "procedure",
                    "duty",
                }:
                    pro_action += confidence
                if overrides:
                    pro_action += confidence * 0.4

        total = pro_action + constraints
        legitimacy = (pro_action / total) if total > 0 else 0.5
        legal_confidence = (sum(confidences) / len(confidences)) if confidences else 0.0

        if legitimacy >= 0.65:
            context = "justified"
        elif legitimacy <= 0.35:
            context = "constrained"
        else:
            context = "contested"

        return max(0.0, min(1.0, legitimacy)), context, len(signals), max(
            0.0, min(1.0, legal_confidence)
        )

    def _apply_legitimacy_adjustment(
        self,
        intent: float,
        legitimacy: float,
        legal_signal_count: int,
    ) -> float:
        """
        Slightly modulate intent with legal-legitimacy when legal signals exist.
        Keeps intent channel dominant while incorporating justification dynamics.
        """
        if legal_signal_count <= 0:
            return intent
        adjustment = (legitimacy - 0.5) * 0.15
        return max(0.0, min(1.0, intent + adjustment))

    def _compute_action_readiness(
        self,
        intent: float,
        capability: float,
        legitimacy: float,
    ) -> float:
        """
        Composite probability proxy:
        capability + intent + legitimacy (legal justification channel).
        """
        score = (intent * 0.4) + (capability * 0.4) + (legitimacy * 0.2)
        return max(0.0, min(1.0, score))


# =====================================================================
# Module-Level Singleton
# =====================================================================

intent_capability_model = IntentCapabilityModel()

__all__ = [
    "IntentCapabilityModel", "intent_capability_model",
    "IntentCapabilityProfile",
    "SignalChannel", "classify_channel", "classify_posture",
    "ACTION_CHANNEL",
]
