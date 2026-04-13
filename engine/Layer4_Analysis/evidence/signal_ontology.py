"""
Canonical Layer-4 signal ontology.

Ministers emit only canonical ``SIG_*`` tokens. Downstream modules can
still interoperate with legacy signal names through alias mappings.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Set

from engine.Layer4_Analysis.evidence.fuzzy_state_interpreter import FuzzyStateInterpreter


# Canonical signal tokens used by minister outputs.
CANONICAL_SIGNALS: List[str] = [
    # Military
    "SIG_MIL_MOBILIZATION",
    "SIG_MIL_LOGISTICS_SURGE",
    "SIG_MIL_EXERCISE_ESCALATION",
    "SIG_MIL_FORWARD_DEPLOYMENT",
    "SIG_MIL_BORDER_CLASHES",
    # Diplomatic
    "SIG_DIP_HOSTILE_RHETORIC",
    "SIG_DIP_CHANNEL_OPEN",
    "SIG_DIP_CHANNEL_CLOSURE",
    "SIG_DIP_DEESCALATION",
    "SIG_DIP_ALLIANCE_COORDINATION",
    # Economic
    "SIG_ECO_SANCTIONS_ACTIVE",
    "SIG_ECO_TRADE_LEVERAGE",
    "SIG_ECO_PRESSURE_HIGH",
    # Domestic
    "SIG_DOM_CIVIL_UNREST",
    "SIG_DOM_REGIME_INSTABILITY",
    "SIG_DOM_PROTEST_PRESSURE",
    # Capability
    "SIG_CAP_SUPPLY_STOCKPILING",
    "SIG_CAP_CYBER_PREPARATION",
    "SIG_CAP_EVACUATION_ACTIVITY",
    # User-directed compact ontology
    "SIG_FORCE_CONCENTRATION",
    "SIG_LOGISTICS_SURGE",
    "SIG_EXERCISE_ESCALATION",
    "SIG_CYBER_PREPARATION",
    "SIG_DIP_HOSTILITY",
    "SIG_NEGOTIATION_BREAKDOWN",
    "SIG_ALLIANCE_ACTIVATION",
    "SIG_ECONOMIC_PRESSURE",
    "SIG_SANCTIONS_ACTIVE",
    "SIG_INTERNAL_INSTABILITY",
    "SIG_PUBLIC_PROTEST",
    "SIG_ELITE_FRACTURE",
    "SIG_MILITARY_DEFECTION",
    "SIG_REGIME_STABLE",
    # Cooperative / de-escalation (GDELT sensor)
    "SIG_DIPLOMACY_ACTIVE",
]

CANONICAL_SIGNAL_SET: Set[str] = set(CANONICAL_SIGNALS)

COMPACT_ONTOLOGY_SIGNALS: List[str] = [
    "SIG_FORCE_CONCENTRATION",
    "SIG_LOGISTICS_SURGE",
    "SIG_EXERCISE_ESCALATION",
    "SIG_CYBER_PREPARATION",
    "SIG_DIP_HOSTILITY",
    "SIG_NEGOTIATION_BREAKDOWN",
    "SIG_ALLIANCE_ACTIVATION",
    "SIG_ECONOMIC_PRESSURE",
    "SIG_SANCTIONS_ACTIVE",
    "SIG_INTERNAL_INSTABILITY",
    "SIG_REGIME_STABLE",
]

PRIMARY_CANONICAL_SIGNALS: List[str] = [
    token for token in CANONICAL_SIGNALS if token not in set(COMPACT_ONTOLOGY_SIGNALS)
]


# Canonical token -> legacy names emitted/consumed by older modules.
CANONICAL_TO_LEGACY: Dict[str, List[str]] = {
    "SIG_MIL_MOBILIZATION": ["troop_staging", "high_mobilization", "SIG_MIL_MOBILIZATION"],
    "SIG_MIL_LOGISTICS_SURGE": ["logistics_movement", "logistics_buildup", "SIG_LOGISTICS_SURGE"],
    "SIG_MIL_EXERCISE_ESCALATION": ["military_exercise", "military_exercises", "recent_exercises", "SIG_EXERCISE_ESCALATION"],
    "SIG_MIL_FORWARD_DEPLOYMENT": ["forward_deployment", "border_positioning", "SIG_FORCE_CONCENTRATION"],
    "SIG_MIL_BORDER_CLASHES": ["border_flare_up", "border_clashes", "skirmishes"],
    "SIG_DIP_HOSTILE_RHETORIC": ["aggressive_rhetoric", "hostility_tone_high", "SIG_DIP_HOSTILITY"],
    "SIG_DIP_CHANNEL_OPEN": ["diplomatic_channel_open", "negotiation_channels_open"],
    "SIG_DIP_CHANNEL_CLOSURE": ["diplomatic_channel_closure", "SIG_NEGOTIATION_BREAKDOWN"],
    "SIG_DIP_DEESCALATION": ["de_escalation_rhetoric"],
    "SIG_DIP_ALLIANCE_COORDINATION": [
        "alliance_coordination",
        "alliance_activity_high",
        "alliance_activation",
        "alliance_realignment",
        "SIG_ALLIANCE_ACTIVATION",
    ],
    "SIG_ECO_SANCTIONS_ACTIVE": ["sanctions_active", "sanctions_pressure", "SIG_SANCTIONS_ACTIVE"],
    "SIG_ECO_TRADE_LEVERAGE": ["trade_dependency_leverage", "trade_dependency_high"],
    "SIG_ECO_PRESSURE_HIGH": ["economic_pressure_high", "economic_crisis", "SIG_ECONOMIC_PRESSURE"],
    "SIG_DOM_CIVIL_UNREST": ["civil_unrest", "domestic_unrest", "SIG_INTERNAL_INSTABILITY"],
    "SIG_DOM_REGIME_INSTABILITY": ["domestic_instability", "regime_instability", "SIG_INTERNAL_INSTABILITY"],
    "SIG_DOM_PROTEST_PRESSURE": ["protest_pressure"],
    "SIG_CAP_SUPPLY_STOCKPILING": ["supply_stockpiling"],
    "SIG_CAP_CYBER_PREPARATION": ["cyber_preparation", "cyber_activity", "SIG_CYBER_PREPARATION"],
    "SIG_CAP_EVACUATION_ACTIVITY": ["evacuation_activity"],
    # Compact ontology aliases
    "SIG_FORCE_CONCENTRATION": ["SIG_MIL_FORWARD_DEPLOYMENT", "troop_staging", "border_positioning"],
    "SIG_LOGISTICS_SURGE": ["SIG_MIL_LOGISTICS_SURGE", "logistics_movement", "logistics_buildup"],
    "SIG_EXERCISE_ESCALATION": ["SIG_MIL_EXERCISE_ESCALATION", "military_exercise", "recent_exercises"],
    "SIG_CYBER_PREPARATION": ["SIG_CAP_CYBER_PREPARATION", "cyber_activity"],
    "SIG_DIP_HOSTILITY": ["SIG_DIP_HOSTILE_RHETORIC", "aggressive_rhetoric", "hostility_tone_high"],
    "SIG_NEGOTIATION_BREAKDOWN": ["SIG_DIP_CHANNEL_CLOSURE", "diplomatic_channel_closure"],
    "SIG_ALLIANCE_ACTIVATION": ["SIG_DIP_ALLIANCE_COORDINATION", "alliance_coordination", "alliance_activity_high"],
    "SIG_ECONOMIC_PRESSURE": ["SIG_ECO_PRESSURE_HIGH", "economic_pressure_high", "economic_crisis"],
    "SIG_SANCTIONS_ACTIVE": ["SIG_ECO_SANCTIONS_ACTIVE", "sanctions_active", "sanctions_pressure"],
    "SIG_INTERNAL_INSTABILITY": ["SIG_DOM_CIVIL_UNREST", "SIG_DOM_REGIME_INSTABILITY", "civil_unrest", "domestic_instability"],
    "SIG_PUBLIC_PROTEST": ["SIG_DOM_PROTEST_PRESSURE", "protest_pressure", "civil_unrest"],
    "SIG_ELITE_FRACTURE": ["SIG_DOM_REGIME_INSTABILITY", "regime_instability"],
    "SIG_MILITARY_DEFECTION": [],
    "SIG_REGIME_STABLE": ["regime_stability_high"],
}

LEGACY_TO_CANONICAL: Dict[str, str] = {}
for canonical_token, legacy_tokens in CANONICAL_TO_LEGACY.items():
    for legacy in legacy_tokens:
        LEGACY_TO_CANONICAL[str(legacy).strip().lower()] = canonical_token


# Phrase-level aliases for noisy LLM outputs.
PHRASE_TO_CANONICAL: Dict[str, str] = {
    "increased cyber attacks": "SIG_CAP_CYBER_PREPARATION",
    "cyber attacks targeting critical infrastructure": "SIG_CAP_CYBER_PREPARATION",
    "deployment of advanced weaponry": "SIG_MIL_FORWARD_DEPLOYMENT",
    "escalation of military operations": "SIG_MIL_EXERCISE_ESCALATION",
    "military mobilization": "SIG_MIL_MOBILIZATION",
    "troop movement": "SIG_MIL_LOGISTICS_SURGE",
    "troop deployment": "SIG_MIL_FORWARD_DEPLOYMENT",
    "hostile rhetoric": "SIG_DIP_HOSTILE_RHETORIC",
    "diplomatic breakdown": "SIG_DIP_CHANNEL_CLOSURE",
    "diplomatic de-escalation": "SIG_DIP_DEESCALATION",
    "sanctions pressure": "SIG_ECO_SANCTIONS_ACTIVE",
    "economic pressure": "SIG_ECO_PRESSURE_HIGH",
    "civil unrest": "SIG_DOM_CIVIL_UNREST",
    "regime instability": "SIG_DOM_REGIME_INSTABILITY",
    "protest escalation": "SIG_DOM_PROTEST_PRESSURE",
    "supply stockpiling": "SIG_CAP_SUPPLY_STOCKPILING",
    "evacuation activity": "SIG_CAP_EVACUATION_ACTIVITY",
    "force concentration": "SIG_FORCE_CONCENTRATION",
    "logistics surge": "SIG_LOGISTICS_SURGE",
    "exercise escalation": "SIG_EXERCISE_ESCALATION",
    "diplomatic hostility": "SIG_DIP_HOSTILITY",
    "negotiation breakdown": "SIG_NEGOTIATION_BREAKDOWN",
    "alliance activation": "SIG_ALLIANCE_ACTIVATION",
    "economic pressure": "SIG_ECONOMIC_PRESSURE",
    "sanctions active": "SIG_SANCTIONS_ACTIVE",
    "internal instability": "SIG_INTERNAL_INSTABILITY",
    "regime stable": "SIG_REGIME_STABLE",
}


# Canonical token -> investigation-friendly descriptor.
CANONICAL_TO_SEARCH_QUERY: Dict[str, str] = {
    "SIG_MIL_MOBILIZATION": "troop mobilization and staging near border areas",
    "SIG_MIL_LOGISTICS_SURGE": "military logistics convoys fuel and supply movement",
    "SIG_MIL_EXERCISE_ESCALATION": "military exercise escalation timeline and scope",
    "SIG_MIL_FORWARD_DEPLOYMENT": "forward military deployment in contested regions",
    "SIG_MIL_BORDER_CLASHES": "border skirmishes clashes and incidents",
    "SIG_DIP_HOSTILE_RHETORIC": "official hostile rhetoric and threat statements",
    "SIG_DIP_CHANNEL_OPEN": "active diplomatic negotiation channels and backchannels",
    "SIG_DIP_CHANNEL_CLOSURE": "diplomatic channel closure or suspension",
    "SIG_DIP_DEESCALATION": "official de-escalation messaging and confidence-building measures",
    "SIG_DIP_ALLIANCE_COORDINATION": "alliance coordination joint statements and exercises",
    "SIG_ECO_SANCTIONS_ACTIVE": "sanctions announcements enforcement and restrictions",
    "SIG_ECO_TRADE_LEVERAGE": "trade dependency leverage and coercive trade signals",
    "SIG_ECO_PRESSURE_HIGH": "economic pressure indicators and macro stress signals",
    "SIG_DOM_CIVIL_UNREST": "civil unrest protests riots and public disorder",
    "SIG_DOM_REGIME_INSTABILITY": "regime instability leadership fractures and governance stress",
    "SIG_DOM_PROTEST_PRESSURE": "protest frequency intensity and escalation indicators",
    "SIG_CAP_SUPPLY_STOCKPILING": "ammunition and military supply stockpiling activity",
    "SIG_CAP_CYBER_PREPARATION": "cyber preparation intrusions and critical infrastructure targeting",
    "SIG_CAP_EVACUATION_ACTIVITY": "civilian or military evacuation activity indicators",
    "SIG_FORCE_CONCENTRATION": "troops deployed OR border deployment",
    "SIG_LOGISTICS_SURGE": "military logistics convoy OR fuel movement",
    "SIG_EXERCISE_ESCALATION": "military exercise escalation timeline",
    "SIG_CYBER_PREPARATION": "cyber attack OR cyber intrusion",
    "SIG_DIP_HOSTILITY": "hostile official statements OR diplomatic threats",
    "SIG_NEGOTIATION_BREAKDOWN": "negotiation collapse OR talks suspended",
    "SIG_ALLIANCE_ACTIVATION": "military alliance OR defense pact",
    "SIG_ECONOMIC_PRESSURE": "economic pressure indicators OR coercive policy",
    "SIG_SANCTIONS_ACTIVE": "sanctions announced OR sanctions enforcement",
    "SIG_INTERNAL_INSTABILITY": "civil unrest OR domestic instability",
    "SIG_REGIME_STABLE": "regime stability indicators OR domestic stability",
}


# Per-minister allowlists to force classification behavior.
MINISTER_SIGNAL_ALLOWLISTS: Dict[str, List[str]] = {
    "security minister": [
        "SIG_MIL_MOBILIZATION",
        "SIG_MIL_LOGISTICS_SURGE",
        "SIG_MIL_EXERCISE_ESCALATION",
        "SIG_MIL_FORWARD_DEPLOYMENT",
        "SIG_MIL_BORDER_CLASHES",
        "SIG_CAP_CYBER_PREPARATION",
    ],
    "economic minister": [
        "SIG_ECO_SANCTIONS_ACTIVE",
        "SIG_ECO_TRADE_LEVERAGE",
        "SIG_ECO_PRESSURE_HIGH",
        "SIG_DIP_ALLIANCE_COORDINATION",
    ],
    "domestic minister": [
        "SIG_DOM_CIVIL_UNREST",
        "SIG_DOM_REGIME_INSTABILITY",
        "SIG_DOM_PROTEST_PRESSURE",
    ],
    "diplomatic minister": [
        "SIG_DIP_HOSTILE_RHETORIC",
        "SIG_DIP_CHANNEL_OPEN",
        "SIG_DIP_CHANNEL_CLOSURE",
        "SIG_DIP_DEESCALATION",
        "SIG_DIP_ALLIANCE_COORDINATION",
    ],
    "strategy minister": [
        "SIG_MIL_MOBILIZATION",
        "SIG_MIL_LOGISTICS_SURGE",
        "SIG_MIL_EXERCISE_ESCALATION",
        "SIG_MIL_FORWARD_DEPLOYMENT",
        "SIG_DIP_HOSTILE_RHETORIC",
        "SIG_DIP_CHANNEL_CLOSURE",
        "SIG_DIP_DEESCALATION",
    ],
    "alliance minister": [
        "SIG_DIP_ALLIANCE_COORDINATION",
        "SIG_DIP_HOSTILE_RHETORIC",
        "SIG_ECO_SANCTIONS_ACTIVE",
        "SIG_ECO_TRADE_LEVERAGE",
    ],
}


DEFAULT_SIGNAL_THRESHOLD = 0.60


def _clip01(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.0


def _make_score_ontology() -> Dict[str, Callable[[Dict[str, float]], float]]:
    return {
        # Military
        "SIG_MIL_MOBILIZATION": lambda f: max(f.get("MIL_HIGH", 0.0), f.get("CAP_TROOP_MOBILIZATION", 0.0)),
        "SIG_MIL_LOGISTICS_SURGE": lambda f: max(
            f.get("CAP_LOGISTICS_ACTIVITY", 0.0),
            f.get("EXERCISE_HIGH", 0.0),
            f.get("MIL_HIGH", 0.0) * 0.7,
        ),
        "SIG_MIL_EXERCISE_ESCALATION": lambda f: f.get("EXERCISE_HIGH", 0.0),
        "SIG_MIL_FORWARD_DEPLOYMENT": lambda f: max(
            f.get("MIL_HIGH", 0.0),
            f.get("CAP_TROOP_MOBILIZATION", 0.0),
            f.get("CLASH_ACTIVITY", 0.0),
        ),
        "SIG_MIL_BORDER_CLASHES": lambda f: f.get("CLASH_ACTIVITY", 0.0),
        # Diplomatic
        "SIG_DIP_HOSTILE_RHETORIC": lambda f: f.get("HOSTILITY_HIGH", 0.0),
        "SIG_DIP_CHANNEL_OPEN": lambda f: min(
            f.get("NEGOTIATION_OPEN", 0.0),
            max(f.get("HOSTILITY_LOW", 0.0), 1.0 - f.get("NEGOTIATION_LOW", 0.0)),
        ),
        "SIG_DIP_CHANNEL_CLOSURE": lambda f: f.get("NEGOTIATION_LOW", 0.0),
        "SIG_DIP_DEESCALATION": lambda f: min(
            f.get("HOSTILITY_LOW", 0.0),
            f.get("NEGOTIATION_OPEN", 0.0),
        ),
        "SIG_DIP_ALLIANCE_COORDINATION": lambda f: f.get("ALLIANCE_ACTIVE", 0.0),
        # Economic
        "SIG_ECO_SANCTIONS_ACTIVE": lambda f: f.get("SANCTIONS_HIGH", 0.0),
        "SIG_ECO_TRADE_LEVERAGE": lambda f: f.get("TRADE_LEVERAGE", 0.0),
        "SIG_ECO_PRESSURE_HIGH": lambda f: max(
            f.get("ECONOMIC_PRESSURE_HIGH", 0.0),
            f.get("SANCTIONS_HIGH", 0.0),
        ),
        # Domestic
        "SIG_DOM_CIVIL_UNREST": lambda f: max(
            f.get("UNREST_HIGH", 0.0),
            f.get("PROTEST_PRESSURE", 0.0),
        ),
        "SIG_DOM_REGIME_INSTABILITY": lambda f: max(
            f.get("REGIME_INSTABILITY", 0.0),
            f.get("UNREST_HIGH", 0.0) * 0.6,
        ),
        "SIG_DOM_PROTEST_PRESSURE": lambda f: f.get("PROTEST_PRESSURE", 0.0),
        # Capability
        "SIG_CAP_SUPPLY_STOCKPILING": lambda f: f.get("CAP_SUPPLY_STOCKPILING", 0.0),
        "SIG_CAP_CYBER_PREPARATION": lambda f: f.get("CAP_CYBER_PREPARATION", 0.0),
        "SIG_CAP_EVACUATION_ACTIVITY": lambda f: f.get("CAP_EVACUATION_ACTIVITY", 0.0),
        # Compact token aliases
        "SIG_FORCE_CONCENTRATION": lambda f: max(
            f.get("MIL_HIGH", 0.0),
            f.get("CAP_TROOP_MOBILIZATION", 0.0),
            f.get("CLASH_ACTIVITY", 0.0),
        ),
        "SIG_LOGISTICS_SURGE": lambda f: max(
            f.get("CAP_LOGISTICS_ACTIVITY", 0.0),
            f.get("EXERCISE_HIGH", 0.0),
            f.get("MIL_HIGH", 0.0) * 0.7,
        ),
        "SIG_EXERCISE_ESCALATION": lambda f: f.get("EXERCISE_HIGH", 0.0),
        "SIG_CYBER_PREPARATION": lambda f: f.get("CAP_CYBER_PREPARATION", 0.0),
        "SIG_DIP_HOSTILITY": lambda f: f.get("HOSTILITY_HIGH", 0.0),
        "SIG_NEGOTIATION_BREAKDOWN": lambda f: f.get("NEGOTIATION_LOW", 0.0),
        "SIG_ALLIANCE_ACTIVATION": lambda f: f.get("ALLIANCE_ACTIVE", 0.0),
        "SIG_ECONOMIC_PRESSURE": lambda f: max(
            f.get("ECONOMIC_PRESSURE_HIGH", 0.0),
            f.get("SANCTIONS_HIGH", 0.0),
        ),
        "SIG_SANCTIONS_ACTIVE": lambda f: f.get("SANCTIONS_HIGH", 0.0),
        "SIG_INTERNAL_INSTABILITY": lambda f: max(
            f.get("REGIME_INSTABILITY", 0.0),
            f.get("UNREST_HIGH", 0.0),
            f.get("PROTEST_PRESSURE", 0.0),
        ),
        "SIG_REGIME_STABLE": lambda f: f.get("REGIME_STABLE_HIGH", 0.0),
    }


SIGNAL_SCORE_ONTOLOGY: Dict[str, Callable[[Dict[str, float]], float]] = _make_score_ontology()


def score_signal_from_interpretation(signal: str, interpreted_state: Dict[str, float]) -> float:
    token = canonicalize_signal_token(signal)
    if not token:
        return 0.0
    rule = SIGNAL_SCORE_ONTOLOGY.get(token)
    if not rule:
        return 0.0
    try:
        return _clip01(rule(interpreted_state or {}))
    except Exception:
        return 0.0


def score_signal(signal: str, state: Any) -> float:
    interpreted = FuzzyStateInterpreter.interpret(state)
    return score_signal_from_interpretation(signal, interpreted)


def check_signal(signal: str, state: Any, threshold: float = DEFAULT_SIGNAL_THRESHOLD) -> bool:
    return score_signal(signal, state) >= _clip01(threshold)


def _build_bool_ontology() -> Dict[str, Callable[[Any], bool]]:
    table: Dict[str, Callable[[Any], bool]] = {}
    for token in CANONICAL_SIGNALS:
        table[token] = (lambda state, _token=token: check_signal(_token, state))
    return table


SIGNAL_ONTOLOGY: Dict[str, Callable[[Any], bool]] = _build_bool_ontology()


def canonicalize_signal_token(value: str) -> Optional[str]:
    """
    Convert a raw signal string to canonical ``SIG_*`` token when possible.
    """
    raw = str(value or "").strip()
    if not raw:
        return None

    if raw in CANONICAL_SIGNAL_SET:
        return raw

    upper_token = raw.upper().replace("-", "_").replace(" ", "_")
    if upper_token in CANONICAL_SIGNAL_SET:
        return upper_token

    lowered = " ".join(raw.lower().split())
    if lowered in LEGACY_TO_CANONICAL:
        return LEGACY_TO_CANONICAL[lowered]

    underscored = lowered.replace(" ", "_")
    if underscored in LEGACY_TO_CANONICAL:
        return LEGACY_TO_CANONICAL[underscored]

    for phrase, canonical in PHRASE_TO_CANONICAL.items():
        if phrase in lowered:
            return canonical

    return None


def normalize_signal_list(
    values: Iterable[str],
    *,
    allowed: Optional[Iterable[str]] = None,
    max_items: int = 6,
) -> List[str]:
    """
    Canonicalize, deduplicate, and optionally constrain to allowlist.
    """
    allowed_set: Optional[Set[str]] = None
    if allowed is not None:
        allowed_set = {
            token
            for token in (
                canonicalize_signal_token(item) or str(item or "").strip()
                for item in allowed
            )
            if token in CANONICAL_SIGNAL_SET
        }

    out: List[str] = []
    seen: Set[str] = set()
    for item in values:
        token = canonicalize_signal_token(str(item or ""))
        if not token:
            continue
        if allowed_set is not None and token not in allowed_set:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
        if len(out) >= max(1, int(max_items)):
            break
    return out


def allowed_signals_for_minister(minister_name: str) -> List[str]:
    """
    Return canonical allowlist for a minister; defaults to full ontology.
    """
    key = str(minister_name or "").strip().lower()
    return list(MINISTER_SIGNAL_ALLOWLISTS.get(key, CANONICAL_SIGNALS))


def legacy_aliases_for_signal(signal: str) -> List[str]:
    token = canonicalize_signal_token(signal)
    if not token:
        return []
    return list(CANONICAL_TO_LEGACY.get(token, []))


def descriptor_for_signal(signal: str) -> str:
    """
    Stable query descriptor for investigation/retrieval.
    """
    token = canonicalize_signal_token(signal)
    if token and token in CANONICAL_TO_SEARCH_QUERY:
        return CANONICAL_TO_SEARCH_QUERY[token]
    fallback = str(signal or "").strip()
    return fallback.replace("_", " ").strip() if fallback else ""


__all__ = [
    "CANONICAL_SIGNALS",
    "CANONICAL_SIGNAL_SET",
    "COMPACT_ONTOLOGY_SIGNALS",
    "PRIMARY_CANONICAL_SIGNALS",
    "CANONICAL_TO_LEGACY",
    "LEGACY_TO_CANONICAL",
    "CANONICAL_TO_SEARCH_QUERY",
    "MINISTER_SIGNAL_ALLOWLISTS",
    "SIGNAL_SCORE_ONTOLOGY",
    "SIGNAL_ONTOLOGY",
    "DEFAULT_SIGNAL_THRESHOLD",
    "canonicalize_signal_token",
    "normalize_signal_list",
    "allowed_signals_for_minister",
    "legacy_aliases_for_signal",
    "descriptor_for_signal",
    "score_signal_from_interpretation",
    "score_signal",
    "check_signal",
]
