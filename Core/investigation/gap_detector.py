"""
Gap detector for bridge-stage investigations (Layer-3 -> MoltBot).

No LLM usage here. This module only diagnoses missing evidence categories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence


EVIDENCE_REQUIREMENTS: Dict[str, List[str]] = {
    "escalation_analysis": ["military", "diplomatic", "legal"],
    "sanctions_analysis": ["economic", "legal", "diplomatic"],
    "war_risk": ["military", "legal", "alliances"],
}


_MILITARY_DRIVER_TOKENS = {
    "threaten_military",
    "military_action",
    "mobilize",
    "blockade",
    "violence",
    "war",
    "pressure",
    "sanction",
    "trade_restriction",
    "attacked",
    "warned",
    "threatened",
}

_DIPLOMATIC_DRIVER_TOKENS = {
    "diplomacy",
    "consultation",
    "consulted",
    "negotiated",
    "statement",
    "made_statement",
    "cooperation",
    "cooperated",
    "aid",
}

MILITARY_MIN_STRENGTH = 0.35
DIPLOMATIC_MIN_STRENGTH = 0.35
LEGAL_MIN_COUNT_DEFAULT = 1
LEGAL_MIN_COUNT_FOR_LEGAL_QUERY = 4


@dataclass
class GapReport:
    question: str
    profile: str
    required_categories: List[str]
    available: Dict[str, bool]
    gaps: List[str]
    reasons: Dict[str, str] = field(default_factory=dict)
    strengths: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "profile": self.profile,
            "required_categories": self.required_categories,
            "available": self.available,
            "gaps": self.gaps,
            "reasons": self.reasons,
            "strengths": self.strengths,
        }


def detect_gaps(
    question: str,
    country_state: Any,
    relationship_state: Any,
) -> List[str]:
    """
    Return only the missing evidence categories.
    """
    return detect_gap_report(question, country_state, relationship_state).gaps


def detect_gap_report(
    question: str,
    country_state: Any,
    relationship_state: Any,
) -> GapReport:
    """
    Diagnose missing knowledge needed for a question profile.
    """
    profile = _select_profile(question)
    required = list(EVIDENCE_REQUIREMENTS.get(profile, EVIDENCE_REQUIREMENTS["escalation_analysis"]))
    states = _as_state_list(country_state)

    legal_count = _sum_legal_signals(states)
    legal_required_min = _required_legal_minimum(question)
    military_strength = _military_strength(relationship_state)
    diplomatic_strength = _diplomatic_strength(relationship_state, states)
    military_present = military_strength >= MILITARY_MIN_STRENGTH
    diplomatic_present = diplomatic_strength >= DIPLOMATIC_MIN_STRENGTH
    economic_present = _detect_economic_presence(states)
    alliances_present = _detect_alliances_presence(states)

    available = {
        "legal": legal_count >= legal_required_min,
        "military": military_present,
        "diplomatic": diplomatic_present,
        "economic": economic_present,
        "alliances": alliances_present,
    }
    reasons: Dict[str, str] = {}
    strengths = {
        "military": round(military_strength, 4),
        "diplomatic": round(diplomatic_strength, 4),
        "legal_signal_count": float(legal_count),
        "legal_required_min": float(legal_required_min),
    }
    gaps: List[str] = []
    for category in required:
        if available.get(category, False):
            continue
        gaps.append(category)
        if category == "legal":
            reasons[category] = (
                "Legal evidence is insufficient "
                f"(count={legal_count} < required={legal_required_min})."
            )
        elif category == "military":
            reasons[category] = (
                "Military indicators are weak "
                f"(strength={military_strength:.2f} < {MILITARY_MIN_STRENGTH:.2f})."
            )
        elif category == "diplomatic":
            reasons[category] = (
                "Diplomatic activity is low "
                f"(strength={diplomatic_strength:.2f} < {DIPLOMATIC_MIN_STRENGTH:.2f})."
            )
        elif category == "economic":
            reasons[category] = "Economic channel confidence/sources are insufficient."
        elif category == "alliances":
            reasons[category] = "Alliance or security-commitment evidence is missing."
        else:
            reasons[category] = "Evidence category not satisfied."

    return GapReport(
        question=question,
        profile=profile,
        required_categories=required,
        available=available,
        gaps=gaps,
        reasons=reasons,
        strengths=strengths,
    )


def _select_profile(question: str) -> str:
    text = str(question or "").lower()
    if any(token in text for token in ("sanction", "tariff", "trade restriction", "export control")):
        return "sanctions_analysis"
    if any(token in text for token in ("war", "conflict", "attack", "escalat", "invasion", "military")):
        return "war_risk"
    return "escalation_analysis"


def _required_legal_minimum(question: str) -> int:
    text = str(question or "").lower()
    legal_tokens = (
        "legal",
        "justification",
        "sovereignty",
        "territorial",
        "principle",
        "treaty",
        "law",
        "article",
    )
    if any(token in text for token in legal_tokens):
        return LEGAL_MIN_COUNT_FOR_LEGAL_QUERY
    return LEGAL_MIN_COUNT_DEFAULT


def _as_state_list(country_state: Any) -> List[Any]:
    if country_state is None:
        return []
    if isinstance(country_state, dict):
        if "states" in country_state and isinstance(country_state["states"], list):
            return list(country_state["states"])
        return [country_state]
    if isinstance(country_state, Sequence) and not isinstance(country_state, (str, bytes)):
        return [item for item in country_state if item is not None]
    return [country_state]


def _sum_legal_signals(states: List[Any]) -> int:
    total = 0
    for state in states:
        total += _legal_signal_count_for_state(state)
    return total


def _legal_signal_count_for_state(state: Any) -> int:
    if state is None:
        return 0

    # Direct attribute access if callers provide legal_signal_count.
    direct = _get_value(state, "legal_signal_count", default=None)
    if isinstance(direct, (int, float)):
        return max(0, int(direct))

    breakdown = _get_nested(
        state,
        ["signal_breakdown", "legal_signals", "signal_count"],
        default=None,
    )
    if isinstance(breakdown, (int, float)):
        return max(0, int(breakdown))

    presence = _get_nested(state, ["legal_justification_presence"], default=None)
    if isinstance(presence, str) and presence.strip().lower() == "active":
        return 1

    return 0


def _military_strength(relationship_state: Any) -> float:
    explicit = _get_value(relationship_state, "military_signaling_present", default=None)
    if isinstance(explicit, bool):
        return 1.0 if explicit else 0.0

    score = _first_numeric(
        relationship_state,
        [
            "military_signaling_score",
            "military_pressure",
            "military_pressure_score",
            "hostility_index",
        ],
    )
    if score is not None:
        return _clamp01(float(score))

    drivers = _read_driver_tokens(relationship_state)
    if not drivers:
        return 0.0
    military_hits = sum(1 for token in drivers if token in _MILITARY_DRIVER_TOKENS)
    if military_hits == 0:
        return 0.20
    return _clamp01(0.25 + (military_hits / max(1, len(drivers))) * 0.75)


def _diplomatic_strength(relationship_state: Any, states: List[Any]) -> float:
    explicit = _get_value(relationship_state, "diplomatic_activity_present", default=None)
    if isinstance(explicit, bool):
        return 1.0 if explicit else 0.0

    score = _first_numeric(
        relationship_state,
        [
            "diplomatic_activity_score",
            "diplomatic_intensity",
            "consultation_index",
        ],
    )
    if score is not None:
        return _clamp01(float(score))

    drivers = _read_driver_tokens(relationship_state)
    if drivers:
        dip_hits = sum(1 for token in drivers if token in _DIPLOMATIC_DRIVER_TOKENS)
        if dip_hits > 0:
            return _clamp01(0.20 + (dip_hits / max(1, len(drivers))) * 0.80)

    # Fallback from country-state diplomatic isolation dimension.
    state_scores: List[float] = []
    for state in states:
        dim = _get_nested(state, ["diplomatic_isolation", "value"], default=None)
        if isinstance(dim, (int, float)):
            # Lower isolation => more diplomatic activity.
            state_scores.append(_clamp01(1.0 - float(dim)))
    if state_scores:
        return sum(state_scores) / len(state_scores)
    return 0.0


def _detect_economic_presence(states: List[Any]) -> bool:
    for state in states:
        confidence = _get_nested(state, ["economic_stress", "confidence"], default=None)
        if isinstance(confidence, (int, float)) and float(confidence) > 0.20:
            return True
        sources = _get_nested(state, ["economic_stress", "contributing_sources"], default=[])
        if isinstance(sources, list) and len(sources) > 0:
            return True
    return False


def _detect_alliances_presence(states: List[Any]) -> bool:
    for state in states:
        evidence_sources = _get_value(state, "evidence_sources", default={})
        if isinstance(evidence_sources, dict):
            keys = {str(k).lower() for k in evidence_sources.keys()}
            if "atop" in keys or "legal_signals" in keys:
                return True
        intent = _get_nested(state, ["signal_breakdown", "intent_capability"], default={})
        if isinstance(intent, dict):
            has_alliance = (
                intent.get("alliance_commitment_activity")
                or intent.get("alliance_commitment")
                or intent.get("legal_signal_activity")
            )
            if bool(has_alliance):
                return True
    return False


def _read_driver_tokens(relationship_state: Any) -> List[str]:
    values = _get_value(relationship_state, "main_drivers", default=[])
    if not isinstance(values, list):
        return []
    tokens: List[str] = []
    for value in values:
        text = str(value or "").strip().lower().replace(" ", "_")
        if text:
            tokens.append(text)
    return tokens


def _first_numeric(container: Any, keys: List[str]) -> Any:
    for key in keys:
        value = _get_value(container, key, default=None)
        if isinstance(value, (int, float)):
            return value
    return None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _get_value(container: Any, key: str, default: Any = None) -> Any:
    if container is None:
        return default
    if isinstance(container, dict):
        return container.get(key, default)
    return getattr(container, key, default)


def _get_nested(container: Any, path: List[str], default: Any = None) -> Any:
    current = container
    for key in path:
        current = _get_value(current, key, default=None)
        if current is None:
            return default
    return current


__all__ = [
    "EVIDENCE_REQUIREMENTS",
    "MILITARY_MIN_STRENGTH",
    "DIPLOMATIC_MIN_STRENGTH",
    "LEGAL_MIN_COUNT_DEFAULT",
    "LEGAL_MIN_COUNT_FOR_LEGAL_QUERY",
    "GapReport",
    "detect_gaps",
    "detect_gap_report",
]
