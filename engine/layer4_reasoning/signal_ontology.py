"""
Layer-4 signal ontology with fuzzy (graded) signal strengths.

Core principle:
continuous state telemetry -> graded symbolic signals in [0, 1].
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from engine.Layer4_Analysis.evidence.signal_ontology import CANONICAL_SIGNALS, canonicalize_signal_token
from engine.Layer4_Analysis.fuzzy import falling, rising


ALLOWED_SIGNALS: List[str] = [
    # Deterministic minister classifier vocabulary.
    "SIG_MIL_ESCALATION",
    "SIG_CYBER_ACTIVITY",
    "SIG_DIP_HOSTILITY",
    "SIG_ALLIANCE_SHIFT",
    "SIG_ECON_PRESSURE",
    "SIG_FORCE_POSTURE",
    "SIG_LOGISTICS_PREP",
    "SIG_DECEPTION_ACTIVITY",
    # Compact ontology.
    "SIG_MIL_MOBILIZATION",
    "SIG_FORCE_CONCENTRATION",
    "SIG_LOGISTICS_SURGE",
    "SIG_EXERCISE_ESCALATION",
    "SIG_CYBER_PREPARATION",
    "SIG_NEGOTIATION_BREAKDOWN",
    "SIG_ALLIANCE_ACTIVATION",
    "SIG_ECONOMIC_PRESSURE",
    "SIG_SANCTIONS_ACTIVE",
    "SIG_INTERNAL_INSTABILITY",
    "SIG_REGIME_STABLE",
    # INTENT crisis-escalation vocabulary.
    "SIG_COERCIVE_PRESSURE",
    "SIG_COERCIVE_BARGAINING",
    "SIG_RETALIATORY_THREAT",
    "SIG_DETERRENCE_SIGNALING",
    # Extended COST / STABILITY.
    "SIG_ECO_SANCTIONS_ACTIVE",
    "SIG_ECO_PRESSURE_HIGH",
    "SIG_DOM_INTERNAL_INSTABILITY",
    # Cooperative / de-escalation (GDELT sensor).
    "SIG_DIPLOMACY_ACTIVE",
    # Kinetic activity composite (confirmed strikes, casualties).
    "SIG_KINETIC_ACTIVITY",
]


def _pick(root: Any, path: str, default: Any = 0.0) -> Any:
    current = root
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            current = getattr(current, key, default)
        if current is default:
            return default
    return current


def _as_float(value: Any, default: float = 0.0) -> float:
    number = _as_number(value, default)
    # Accept percentage-like inputs (e.g., 65 -> 0.65) while preserving [0,1] values.
    if number > 1.0 and number <= 100.0:
        number = number / 100.0
    return max(0.0, min(1.0, number))


def _as_number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"high", "active", "true", "yes"}:
            return 1.0
        if token in {"medium", "moderate"}:
            return 0.6
        if token in {"low", "inactive", "none", "false", "no"}:
            return 0.0
    try:
        return float(value)
    except Exception:
        return float(default)


def _normalize_count(value: Any, full_scale: float) -> float:
    if isinstance(value, int) and not isinstance(value, bool):
        denom = full_scale if full_scale > 0 else 1.0
        return max(0.0, min(1.0, float(value) / denom))
    number = _as_number(value, 0.0)
    # If already normalized, preserve; otherwise compress by scale.
    if number <= 1.0:
        return max(0.0, min(1.0, number))
    denom = full_scale if full_scale > 0 else 1.0
    return max(0.0, min(1.0, number / denom))


def _clip01(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.0


def interpret_state(state: Any) -> Dict[str, float]:
    """
    Interpret raw state values into graded signal strengths.
    """
    mobilization = max(
        _as_float(_pick(state, "military.mobilization", 0.0), 0.0),
        _as_float(_pick(state, "military.mobilization_level", 0.0), 0.0),
    )
    exercises_raw = _as_number(_pick(state, "military.exercises", 0.0), 0.0)
    border_activity = max(
        _as_float(_pick(state, "military.border_activity", 0.0), 0.0),
        _normalize_count(_pick(state, "military.clash_history", 0.0), 5.0),
    )
    hostility = max(
        _as_float(_pick(state, "diplomatic.hostility", 0.0), 0.0),
        _as_float(_pick(state, "diplomatic.hostility_tone", 0.0), 0.0),
    )
    negotiations = _as_float(_pick(state, "diplomatic.negotiations", 0.0), 0.0)
    alliances = max(
        _as_float(_pick(state, "diplomatic.alliances", 0.0), 0.0),
        _as_float(_pick(state, "diplomatic.alliance_activity", 0.0), 0.0),
    )
    economic_pressure = _as_float(_pick(state, "economic.economic_pressure", 0.0), 0.0)
    sanctions = max(
        _as_float(_pick(state, "economic.sanctions", 0.0), 0.0),
        _as_float(_pick(state, "economic.sanctions_pressure", 0.0), 0.0),
    )
    unrest = _as_float(_pick(state, "domestic.unrest", 0.0), 0.0)
    regime_stability = _as_float(_pick(state, "domestic.regime_stability", 0.5), 0.5)

    logistics_activity = max(
        _as_float(_pick(state, "capability.logistics_activity", 0.0), 0.0),
        _as_float(_pick(state, "capabilities.logistics_activity", 0.0), 0.0),
        _as_float(_pick(state, "capabilities.logistics", 0.0), 0.0),
    )
    cyber_activity = max(
        _as_float(_pick(state, "capability.cyber_activity", 0.0), 0.0),
        _as_float(_pick(state, "capabilities.cyber_activity", 0.0), 0.0),
        _as_float(_pick(state, "capabilities.cyber", 0.0), 0.0),
    )

    # Exercises may arrive as either count (e.g., 3) or normalized (e.g., 0.6).
    exercise_input = exercises_raw if exercises_raw > 1.0 else (exercises_raw * 5.0)
    exercise_norm = rising(exercise_input, 1.0, 5.0)
    border_norm = rising(border_activity, 0.30, 0.75)

    strengths: Dict[str, float] = {
        "SIG_MIL_MOBILIZATION": rising(mobilization, 0.40, 0.80),
        "SIG_FORCE_CONCENTRATION": max(
            rising(mobilization, 0.45, 0.80),
            border_norm,
        ),
        "SIG_LOGISTICS_SURGE": max(
            rising(logistics_activity, 0.45, 0.75),
            exercise_norm * 0.7,
        ),
        "SIG_EXERCISE_ESCALATION": exercise_norm,
        "SIG_CYBER_PREPARATION": rising(cyber_activity, 0.45, 0.75),
        "SIG_DIP_HOSTILITY": rising(hostility, 0.50, 0.85),
        "SIG_NEGOTIATION_BREAKDOWN": falling(negotiations, 0.25, 0.75),
        "SIG_ALLIANCE_ACTIVATION": rising(alliances, 0.45, 0.80),
        "SIG_ECONOMIC_PRESSURE": rising(max(economic_pressure, sanctions), 0.35, 0.75),
        "SIG_SANCTIONS_ACTIVE": rising(sanctions, 0.30, 0.70),
        "SIG_INTERNAL_INSTABILITY": rising(unrest, 0.30, 0.70),
        "SIG_REGIME_STABLE": max(
            rising(regime_stability, 0.55, 0.85),
            falling(unrest, 0.20, 0.60),
        ),
    }

    strengths["SIG_MIL_ESCALATION"] = max(
        strengths["SIG_MIL_MOBILIZATION"],
        strengths["SIG_FORCE_CONCENTRATION"],
        strengths["SIG_LOGISTICS_SURGE"],
    )
    strengths["SIG_CYBER_ACTIVITY"] = strengths["SIG_CYBER_PREPARATION"]
    strengths["SIG_ALLIANCE_SHIFT"] = strengths["SIG_ALLIANCE_ACTIVATION"]
    strengths["SIG_ECON_PRESSURE"] = strengths["SIG_ECONOMIC_PRESSURE"]
    strengths["SIG_FORCE_POSTURE"] = max(
        strengths["SIG_FORCE_CONCENTRATION"],
        strengths["SIG_MIL_MOBILIZATION"],
    )
    strengths["SIG_LOGISTICS_PREP"] = strengths["SIG_LOGISTICS_SURGE"]
    strengths["SIG_DECEPTION_ACTIVITY"] = _clip01(
        (0.6 * strengths["SIG_MIL_ESCALATION"])
        + (0.4 * strengths["SIG_NEGOTIATION_BREAKDOWN"])
    )

    # INTENT crisis-escalation signals (pressure → coercion → signaling → crisis)
    # SIG_COERCIVE_PRESSURE: high sanctions + hostility → coercive leverage
    strengths["SIG_COERCIVE_PRESSURE"] = _clip01(
        max(sanctions, economic_pressure) * rising(hostility, 0.20, 0.60)
        + rising(sanctions, 0.35, 0.70) * 0.5
    )
    # SIG_COERCIVE_BARGAINING: sanctions/pressure combined with diplomatic hostility
    strengths["SIG_COERCIVE_BARGAINING"] = _clip01(
        0.5 * rising(max(sanctions, economic_pressure), 0.30, 0.65)
        + 0.5 * rising(hostility, 0.25, 0.65)
    )
    # SIG_RETALIATORY_THREAT: military posture + hostility = threatening retaliation
    strengths["SIG_RETALIATORY_THREAT"] = _clip01(
        0.5 * rising(mobilization, 0.40, 0.75)
        + 0.5 * rising(hostility, 0.35, 0.70)
    )
    # SIG_DETERRENCE_SIGNALING: force posture + alliance activity = signaling resolve
    strengths["SIG_DETERRENCE_SIGNALING"] = _clip01(
        0.4 * strengths["SIG_FORCE_POSTURE"]
        + 0.3 * strengths["SIG_ALLIANCE_ACTIVATION"]
        + 0.3 * strengths["SIG_CYBER_ACTIVITY"]
    )
    # ── Kinetic Activity composite ──────────────────────────────
    # SIG_KINETIC_ACTIVITY: confirmed strikes, casualties, infrastructure
    # damage.  Real war, not rhetoric.  Activates when multiple kinetic
    # indicators co-occur.  Prioritised above pure mobilisation.
    strike_indicators = max(
        _as_float(_pick(state, "military.strikes", 0.0), 0.0),
        _as_float(_pick(state, "military.airstrikes", 0.0), 0.0),
        _as_float(_pick(state, "military.kinetic_activity", 0.0), 0.0),
    )
    casualty_indicators = _as_float(_pick(state, "military.casualties", 0.0), 0.0)
    infra_damage = _as_float(_pick(state, "military.infrastructure_damage", 0.0), 0.0)
    retaliation = max(
        _as_float(_pick(state, "military.retaliation", 0.0), 0.0),
        _as_float(_pick(state, "diplomatic.retaliatory_statement", 0.0), 0.0),
    )
    blockade = _as_float(_pick(state, "military.blockade", 0.0), 0.0)
    airspace_closure = _as_float(_pick(state, "military.airspace_closure", 0.0), 0.0)

    kinetic_score = 0.0
    kinetic_sources = sum(1 for v in [strike_indicators, casualty_indicators,
                                       infra_damage, retaliation, blockade,
                                       airspace_closure] if v > 0.3)
    if kinetic_sources >= 2:
        kinetic_score = max(kinetic_score, 0.90)
    if strike_indicators > 0.5 and infra_damage > 0.3:
        kinetic_score = max(kinetic_score, 0.85)
    if strike_indicators > 0.3 and retaliation > 0.3:
        kinetic_score = max(kinetic_score, 0.80)
    if casualty_indicators > 0.3 and strike_indicators > 0.3:
        kinetic_score = max(kinetic_score, 0.80)
    if blockade > 0.5 or airspace_closure > 0.5:
        kinetic_score = max(kinetic_score, 0.70)
    # Single strong strike indicator still registers
    if strike_indicators > 0.6:
        kinetic_score = max(kinetic_score, 0.65)
    strengths["SIG_KINETIC_ACTIVITY"] = _clip01(kinetic_score)

    # Extended COST / STABILITY aliases
    strengths["SIG_ECO_SANCTIONS_ACTIVE"] = strengths["SIG_SANCTIONS_ACTIVE"]
    strengths["SIG_ECO_PRESSURE_HIGH"] = strengths["SIG_ECONOMIC_PRESSURE"]
    strengths["SIG_DOM_INTERNAL_INSTABILITY"] = strengths["SIG_INTERNAL_INSTABILITY"]

    # Compatibility aliases for older modules/tests.
    strengths.update(
        {
            "SIG_MIL_LOGISTICS_SURGE": strengths["SIG_LOGISTICS_SURGE"],
            "SIG_MIL_EXERCISE_ESCALATION": strengths["SIG_EXERCISE_ESCALATION"],
            "SIG_MIL_FORWARD_DEPLOYMENT": strengths["SIG_FORCE_CONCENTRATION"],
            "SIG_MIL_BORDER_CLASHES": strengths["SIG_FORCE_CONCENTRATION"],
            "SIG_DIP_HOSTILE_RHETORIC": strengths["SIG_DIP_HOSTILITY"],
            "SIG_DIP_CHANNEL_OPEN": 1.0 - strengths["SIG_NEGOTIATION_BREAKDOWN"],
            "SIG_DIP_CHANNEL_CLOSURE": strengths["SIG_NEGOTIATION_BREAKDOWN"],
            "SIG_DIP_DEESCALATION": 1.0 - strengths["SIG_DIP_HOSTILITY"],
            "SIG_DIP_ALLIANCE_COORDINATION": strengths["SIG_ALLIANCE_ACTIVATION"],
            "SIG_ECO_SANCTIONS_ACTIVE": strengths["SIG_SANCTIONS_ACTIVE"],
            "SIG_ECO_TRADE_LEVERAGE": strengths["SIG_ECONOMIC_PRESSURE"],
            "SIG_ECO_PRESSURE_HIGH": strengths["SIG_ECONOMIC_PRESSURE"],
            "SIG_DOM_CIVIL_UNREST": strengths["SIG_INTERNAL_INSTABILITY"],
            "SIG_DOM_REGIME_INSTABILITY": strengths["SIG_INTERNAL_INSTABILITY"],
            "SIG_DOM_PROTEST_PRESSURE": strengths["SIG_INTERNAL_INSTABILITY"],
            "SIG_CAP_SUPPLY_STOCKPILING": strengths["SIG_MIL_ESCALATION"],
            "SIG_CAP_CYBER_PREPARATION": strengths["SIG_CYBER_PREPARATION"],
            "SIG_CAP_EVACUATION_ACTIVITY": strengths["SIG_MIL_ESCALATION"],
        }
    )

    return {k: _clip01(v) for k, v in strengths.items()}


def compute_signal_strengths(state: Any) -> Dict[str, float]:
    return interpret_state(state)


_KNOWN_TOKENS: List[str] = list(
    dict.fromkeys(list(ALLOWED_SIGNALS) + list(CANONICAL_SIGNALS) + list(compute_signal_strengths({}).keys()))
)
FUZZY_SIGNAL_ONTOLOGY: Dict[str, Any] = {
    token: (lambda state, _token=token: compute_signal_strengths(state).get(_token, 0.0))
    for token in _KNOWN_TOKENS
}
SIGNAL_ONTOLOGY = FUZZY_SIGNAL_ONTOLOGY


def _normalize_signal_token(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    token = canonicalize_signal_token(raw)
    if token and token in SIGNAL_ONTOLOGY:
        return token
    candidate = raw.upper().replace("-", "_").replace(" ", "_")
    if candidate in SIGNAL_ONTOLOGY:
        return candidate
    return ""


def validate_signals(output: Dict[str, Any]) -> Dict[str, Any]:
    parsed = dict(output or {})
    values = parsed.get("predicted_signals", [])
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        values = []

    valid: List[str] = []
    seen = set()
    for item in values:
        token = _normalize_signal_token(item)
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        valid.append(token)

    parsed["predicted_signals"] = valid
    return parsed


def verify_signals(predicted_signals: Iterable[str], state_context: Any) -> float:
    signals: List[str] = []
    for item in list(predicted_signals or []):
        token = _normalize_signal_token(item)
        if token:
            signals.append(token)
    if not signals:
        return 0.0

    strengths = compute_signal_strengths(state_context)
    score = 0.0
    for sig in signals:
        score += _clip01(strengths.get(sig, 0.0))
    return score / len(signals)


__all__ = [
    "ALLOWED_SIGNALS",
    "FUZZY_SIGNAL_ONTOLOGY",
    "SIGNAL_ONTOLOGY",
    "interpret_state",
    "compute_signal_strengths",
    "validate_signals",
    "verify_signals",
]
