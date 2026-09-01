"""DIP-native fuzzy signal-to-risk estimation.

This module is the next-gen SRE contract:
StateContext -> SignalBelief -> ObservedSignal -> domain fusion -> risk.
It is deliberately empirical. Legal/RAG-derived material can constrain or
explain a decision, but it is excluded from escalation scoring.
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import prod
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, Field


def _clip01(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return max(0.0, min(1.0, float(default)))


def triangular(x: Any, a: float, b: float, c: float) -> float:
    """Triangular fuzzy membership bounded to [0, 1]."""

    x = _clip01(x)
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if x < b:
        return _clip01((x - a) / (b - a) if b != a else 1.0)
    return _clip01((c - x) / (c - b) if c != b else 1.0)


def trapezoidal(x: Any, a: float, b: float, c: float, d: float) -> float:
    """Trapezoidal fuzzy membership bounded to [0, 1]."""

    x = _clip01(x)
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if x < b:
        return _clip01((x - a) / (b - a) if b != a else 1.0)
    return _clip01((d - x) / (d - c) if d != c else 1.0)


def rising(x: Any, low: float, high: float) -> float:
    """Rising linear membership bounded to [0, 1]."""

    x = _clip01(x)
    if x <= low:
        return 0.0
    if x >= high:
        return 1.0
    return _clip01((x - low) / (high - low) if high != low else 1.0)


def falling(x: Any, low: float, high: float) -> float:
    """Falling linear membership bounded to [0, 1]."""

    x = _clip01(x)
    if x <= low:
        return 1.0
    if x >= high:
        return 0.0
    return _clip01(1.0 - ((x - low) / (high - low)) if high != low else 0.0)


SOURCE_RELIABILITY = {
    "SOCIAL": 0.30,
    "OSINT": 0.55,
    "MOLTBOT": 0.55,
    "NEWS": 0.58,
    "REUTERS": 0.70,
    "BBC": 0.68,
    "GOV": 0.75,
    "UN": 0.80,
    "SIPRI": 0.85,
    "SENSOR": 0.90,
    "SATELLITE": 0.90,
    "SIGINT": 0.86,
    "HUMINT": 0.78,
    "ANALYST": 0.72,
    "DATASET": 0.90,
}


SIGNAL_ONTOLOGY: Dict[str, Dict[str, Any]] = {
    "MIL_MOBILIZATION": {
        "aliases": ("MOBILIZATION", "FORCE_DEPLOYMENT", "TROOP_MOVEMENT", "FORCE_POSTURE"),
        "fuzzy_set": "mobilization",
        "domain_weights": {"capability": 0.95, "intent": 0.45, "stability": 0.15, "cost": 0.10},
        "membership": lambda x: rising(x, 0.30, 0.82),
    },
    "LOGISTICS_PREP": {
        "aliases": ("LOGISTICS", "SUPPLY", "FUEL", "AMMUNITION", "RAILHEAD"),
        "fuzzy_set": "mobilization",
        "domain_weights": {"capability": 0.82, "intent": 0.35, "stability": 0.10, "cost": 0.12},
        "membership": lambda x: rising(x, 0.25, 0.76),
    },
    "HOSTILITY": {
        "aliases": ("HOSTIL", "THREAT", "ESCALATION", "CLASH", "KINETIC", "MISSILE", "ATTACK"),
        "fuzzy_set": "hostility",
        "domain_weights": {"capability": 0.35, "intent": 0.95, "stability": 0.35, "cost": 0.10},
        "membership": lambda x: rising(x, 0.22, 0.72),
    },
    "SANCTIONS": {
        "aliases": ("SANCTION", "ECONOMIC_PRESSURE", "EXPORT_CONTROL", "ASSET_FREEZE"),
        "fuzzy_set": "sanctions",
        "domain_weights": {"capability": 0.05, "intent": 0.35, "stability": 0.20, "cost": 0.95},
        "membership": lambda x: rising(x, 0.25, 0.75),
    },
    "NEGOTIATION": {
        "aliases": ("NEGOTIATION", "DIPLOMACY", "TALK", "BACKCHANNEL", "DEESCALATION"),
        "fuzzy_set": "negotiation",
        "domain_weights": {"capability": 0.0, "intent": -0.30, "stability": -0.35, "cost": -0.10},
        "membership": lambda x: rising(x, 0.20, 0.70),
    },
    "INSTABILITY": {
        "aliases": ("UNREST", "INSTAB", "PROTEST", "RIOT", "COUP", "DOMESTIC"),
        "fuzzy_set": "instability",
        "domain_weights": {"capability": 0.05, "intent": 0.15, "stability": 0.95, "cost": 0.35},
        "membership": lambda x: rising(x, 0.20, 0.70),
    },
    "EXERCISES": {
        "aliases": ("EXERCISE", "DRILL", "WARGAME"),
        "fuzzy_set": "exercises",
        "domain_weights": {"capability": 0.62, "intent": 0.22, "stability": 0.10, "cost": 0.08},
        "membership": lambda x: trapezoidal(x, 0.15, 0.45, 0.85, 1.0),
    },
    "CYBER_PRESSURE": {
        "aliases": ("CYBER", "DDOS", "MALWARE", "INTRUSION"),
        "fuzzy_set": "hostility",
        "domain_weights": {"capability": 0.35, "intent": 0.70, "stability": 0.35, "cost": 0.20},
        "membership": lambda x: rising(x, 0.20, 0.72),
    },
    "DIPLOMATIC_BREAKDOWN": {
        "aliases": ("BREAKDOWN", "RECALL_AMBASSADOR", "EXPEL", "TREATY_SUSPEND"),
        "fuzzy_set": "hostility",
        "domain_weights": {"capability": 0.05, "intent": 0.72, "stability": 0.28, "cost": 0.50},
        "membership": lambda x: rising(x, 0.25, 0.75),
    },
}


LEGAL_FIREWALL_TOKENS = (
    "LEGAL",
    "LAW",
    "COURT",
    "TREATY_INTERPRETATION",
    "RAG",
    "LEGAL_RAG",
    "EVIDENCE_CHAIN",
    "VERIFICATION_CHAIN",
    "FIREWALL",
)


class SignalBelief(BaseModel):
    signal_code: str
    fuzzy_set: str = "unknown"
    membership: float = 0.0
    reliability: float = 0.0
    recency: float = 1.0
    evidence_support: float = 0.0
    source_agreement: float = 0.0
    temporal_stability: float = 0.0
    uncertainty: float = 0.0
    source_count: int = 0
    source_types: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    eligible_for_sre: bool = True
    exclusion_reason: Optional[str] = None
    fuzzy_memberships: Dict[str, float] = Field(default_factory=dict)


class ObservedSignal(BaseModel):
    signal_code: str
    domain: str = "unknown"
    membership: float = 0.0
    reliability: float = 0.0
    recency: float = 1.0
    evidence_support: float = 0.0
    confidence: float = 0.0
    fuzzy_memberships: Dict[str, float] = Field(default_factory=dict)
    source_refs: List[str] = Field(default_factory=list)
    excluded_from_sre: bool = False
    exclusion_reason: Optional[str] = None


class SREDomains(BaseModel):
    capability: float = 0.0
    intent: float = 0.0
    stability: float = 0.0
    cost: float = 0.0
    contributors: Dict[str, List[str]] = Field(default_factory=dict)

    @property
    def instability(self) -> float:
        return self.stability


class EscalationInput(BaseModel):
    base_score: float = 0.0
    trend_bonus: float = 0.0
    temporal_spike_bonus: float = 0.0
    mobilization_trigger: bool = False
    mobilization_bonus: float = 0.0
    logistics_trigger: bool = False
    logistics_bonus: float = 0.0
    capability_floor_applied: bool = False
    conflict_floor_applied: bool = False
    confidence_decay: float = 1.0
    active_conflicts: List[str] = Field(default_factory=list)


class SREAssessment(BaseModel):
    fuzzy_memberships: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    signal_beliefs: List[SignalBelief] = Field(default_factory=list)
    projected_signals: List[ObservedSignal] = Field(default_factory=list)
    sre_domains: SREDomains = Field(default_factory=SREDomains)
    sre_input: EscalationInput = Field(default_factory=EscalationInput)
    sre_escalation_score: float = 0.0
    risk_level: str = "LOW"
    qualitative_bands: Dict[str, str] = Field(default_factory=dict)
    escalation_trace: List[Dict[str, Any]] = Field(default_factory=list)
    legal_firewall_rejections: List[Dict[str, str]] = Field(default_factory=list)


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _source_ref(signal: Any) -> str:
    return str(_get(signal, "source_ref", "") or _get(signal, "source", "") or "")


def _source_type(ref: str) -> str:
    clean = (ref or "OSINT").upper().replace("-", "_").replace(" ", "_")
    for token in SOURCE_RELIABILITY:
        if clean.startswith(token) or token in clean:
            return token
    return clean.split("_", 1)[0] if clean else "OSINT"


def _source_reliability(ref: str, fallback: Any = None) -> float:
    if fallback is not None:
        return _clip01(fallback, SOURCE_RELIABILITY["OSINT"])
    return _clip01(SOURCE_RELIABILITY.get(_source_type(ref), SOURCE_RELIABILITY["OSINT"]))


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _recency_weight(values: Sequence[Any], now: Optional[datetime] = None) -> float:
    parsed = [_parse_timestamp(value) for value in values]
    parsed = [value for value in parsed if value is not None]
    if not parsed:
        return 1.0
    now = now or datetime.now(timezone.utc)
    age_hours = min(max(0.0, (now - stamp).total_seconds() / 3600.0) for stamp in parsed)
    return _clip01(0.5 ** (age_hours / 72.0))


def canonicalize_signal_token(action: Any) -> str:
    token = str(action or "").upper().replace("-", "_").replace(" ", "_")
    token = token.removeprefix("SIG_")
    token = token.removeprefix("SIGNAL_")
    for canonical, spec in SIGNAL_ONTOLOGY.items():
        if canonical in token:
            return canonical
        if any(alias in token for alias in spec.get("aliases", ())):
            return canonical
    return token or "UNKNOWN"


def _ontology_spec(signal_code: str) -> Dict[str, Any]:
    return SIGNAL_ONTOLOGY.get(signal_code, {
        "fuzzy_set": "unknown",
        "domain_weights": {"capability": 0.15, "intent": 0.15, "stability": 0.15, "cost": 0.15},
        "membership": lambda x: rising(x, 0.25, 0.75),
    })


def _signal_memberships(signal_code: str, intensity: float) -> Dict[str, float]:
    spec = _ontology_spec(signal_code)
    fuzzy_set = str(spec.get("fuzzy_set", "unknown"))
    primary = _clip01(spec.get("membership", lambda x: x)(intensity))
    memberships = {fuzzy_set: primary}
    memberships.setdefault("mobilization", rising(intensity, 0.30, 0.82))
    memberships.setdefault("hostility", rising(intensity, 0.22, 0.72))
    memberships.setdefault("sanctions", rising(intensity, 0.25, 0.75))
    memberships.setdefault("negotiation", rising(intensity, 0.20, 0.70))
    memberships.setdefault("instability", rising(intensity, 0.20, 0.70))
    memberships.setdefault("exercises", trapezoidal(intensity, 0.15, 0.45, 0.85, 1.0))
    return {key: round(_clip01(value), 4) for key, value in memberships.items()}


def _is_firewalled(signal: Any, signal_code: str) -> Tuple[bool, Optional[str]]:
    haystack = " ".join(
        [
            signal_code,
            str(_get(signal, "domain", "")),
            str(_get(signal, "verification_status", "")),
            _source_ref(signal),
        ]
    ).upper()
    if any(token in haystack for token in LEGAL_FIREWALL_TOKENS):
        return True, "legal_or_rag_material_excluded_from_empirical_sre"
    return False, None


def _source_agreement(source_types: Iterable[str]) -> float:
    count = len(set(source_types))
    if count <= 0:
        return 0.0
    return _clip01(0.45 + (count * 0.15))


def _temporal_stability(signal_code: str, temporal_indicators: Sequence[Any]) -> float:
    for item in temporal_indicators:
        if canonicalize_signal_token(_get(item, "signal", "")) == signal_code:
            persistence = _clip01(_get(item, "persistence", 0.0))
            if str(_get(item, "trend_label", "")).lower() == "accelerating":
                return _clip01(max(persistence, 0.65))
            return _clip01(persistence or 0.5)
    return 0.5


class SignalBeliefModel:
    """Convert raw telemetry and existing beliefs into graded signal beliefs."""

    def evaluate(self, state_context: Any) -> List[SignalBelief]:
        signals = list(_get(state_context, "current_signals", []) or [])
        temporal = list(_get(state_context, "temporal_indicators", []) or [])
        grouped: Dict[str, List[Any]] = {}
        for signal in signals:
            token = canonicalize_signal_token(_get(signal, "action", _get(signal, "signal", "")))
            grouped.setdefault(token, []).append(signal)

        beliefs: List[SignalBelief] = []
        for signal_code, group in grouped.items():
            refs = [_source_ref(item) for item in group]
            source_types = [_source_type(ref) for ref in refs]
            reliability = max(
                _source_reliability(_source_ref(item), _get(item, "reliability_score", None))
                for item in group
            )
            support = max(_clip01(_get(item, "confidence", 0.0)) for item in group)
            support = _clip01(support + min(0.20, max(0, len(set(source_types)) - 1) * 0.08))
            recency = _recency_weight([_get(item, "timestamp", None) for item in group])
            intensity = max(_clip01(_get(item, "intensity", _get(item, "membership", 0.0))) for item in group)
            memberships = _signal_memberships(signal_code, intensity)
            spec = _ontology_spec(signal_code)
            membership = memberships.get(str(spec.get("fuzzy_set", "unknown")), max(memberships.values()))
            temporal_stability = _temporal_stability(signal_code, temporal)
            agreement = _source_agreement(source_types)
            firewalled, reason = next(
                ((_is_firewalled(item, signal_code)) for item in group if _is_firewalled(item, signal_code)[0]),
                (False, None),
            )
            beliefs.append(
                SignalBelief(
                    signal_code=signal_code,
                    fuzzy_set=str(spec.get("fuzzy_set", "unknown")),
                    membership=round(membership, 4),
                    reliability=round(reliability, 4),
                    recency=round(recency, 4),
                    evidence_support=round(support, 4),
                    source_agreement=round(agreement, 4),
                    temporal_stability=round(temporal_stability, 4),
                    uncertainty=round(_clip01(1.0 - ((support + agreement + temporal_stability) / 3.0)), 4),
                    source_count=len(group),
                    source_types=sorted(set(source_types)),
                    evidence_refs=[ref for ref in refs if ref],
                    eligible_for_sre=not firewalled,
                    exclusion_reason=reason,
                    fuzzy_memberships=memberships,
                )
            )

        existing_beliefs = list(_get(state_context, "beliefs", []) or [])
        known = {belief.signal_code for belief in beliefs}
        for belief in existing_beliefs:
            signal_code = canonicalize_signal_token(_get(belief, "signal_code", ""))
            if signal_code in known:
                continue
            support = _clip01(_get(belief, "support_score", 0.0))
            spec = _ontology_spec(signal_code)
            memberships = _signal_memberships(signal_code, support)
            firewalled, reason = _is_firewalled({"source_ref": ",".join(_get(belief, "source_types", []) or [])}, signal_code)
            beliefs.append(
                SignalBelief(
                    signal_code=signal_code,
                    fuzzy_set=str(spec.get("fuzzy_set", "unknown")),
                    membership=round(memberships.get(str(spec.get("fuzzy_set", "unknown")), support), 4),
                    reliability=round(_clip01(max([SOURCE_RELIABILITY.get(str(src).upper(), 0.55) for src in (_get(belief, "source_types", []) or ["OSINT"])])), 4),
                    recency=round(_clip01(_get(belief, "recency_weight", 1.0), 1.0), 4),
                    evidence_support=round(support, 4),
                    source_agreement=round(_source_agreement(_get(belief, "source_types", []) or ["OSINT"]), 4),
                    temporal_stability=round(_temporal_stability(signal_code, temporal), 4),
                    uncertainty=round(_clip01(1.0 - support), 4),
                    source_count=int(_get(belief, "source_count", 1) or 1),
                    source_types=list(_get(belief, "source_types", []) or ["OSINT"]),
                    eligible_for_sre=not firewalled,
                    exclusion_reason=reason,
                    fuzzy_memberships=memberships,
                )
            )
        return sorted(beliefs, key=lambda item: item.membership * item.evidence_support, reverse=True)


def build_signal_beliefs(state_context: Any) -> List[SignalBelief]:
    return SignalBeliefModel().evaluate(state_context)


def project_state_to_observed_signals(state_context: Any) -> List[ObservedSignal]:
    projected = []
    for belief in build_signal_beliefs(state_context):
        confidence = _clip01(belief.membership * belief.reliability * belief.recency * belief.evidence_support)
        weights = _ontology_spec(belief.signal_code).get("domain_weights", {})
        primary_domain = max((key for key, value in weights.items() if value > 0), key=lambda key: weights[key], default="unknown")
        projected.append(
            ObservedSignal(
                signal_code=belief.signal_code,
                domain=primary_domain,
                membership=belief.membership,
                reliability=belief.reliability,
                recency=belief.recency,
                evidence_support=belief.evidence_support,
                confidence=round(confidence, 4),
                fuzzy_memberships=belief.fuzzy_memberships,
                source_refs=belief.evidence_refs,
                excluded_from_sre=not belief.eligible_for_sre,
                exclusion_reason=belief.exclusion_reason,
            )
        )
    return projected


def _fuzzy_or(values: Iterable[float]) -> float:
    clean = [_clip01(value) for value in values]
    if not clean:
        return 0.0
    return _clip01(1.0 - prod(1.0 - value for value in clean))


def compute_domain_fusion(projected_signals: Sequence[ObservedSignal]) -> SREDomains:
    domain_values: Dict[str, List[Tuple[str, float]]] = {"capability": [], "intent": [], "stability": [], "cost": []}
    for signal in projected_signals:
        if signal.excluded_from_sre:
            continue
        weights = _ontology_spec(signal.signal_code).get("domain_weights", {})
        for domain in domain_values:
            weight = float(weights.get(domain, 0.0) or 0.0)
            value = signal.confidence * abs(weight)
            if weight < 0:
                value *= -0.65
            domain_values[domain].append((signal.signal_code, value))

    fused: Dict[str, float] = {}
    contributors: Dict[str, List[str]] = {}
    for domain, values in domain_values.items():
        positive = [value for _, value in values if value > 0]
        negative = [abs(value) for _, value in values if value < 0]
        score = _clip01(_fuzzy_or(positive) - min(0.35, _fuzzy_or(negative)))
        fused[domain] = round(score, 4)
        contributors[domain] = [name for name, value in sorted(values, key=lambda item: abs(item[1]), reverse=True) if abs(value) > 0.01][:5]

    return SREDomains(
        capability=fused["capability"],
        intent=fused["intent"],
        stability=fused["stability"],
        cost=fused["cost"],
        contributors=contributors,
    )


def _temporal_bonuses(state_context: Any) -> Tuple[float, float]:
    indicators = list(_get(state_context, "temporal_indicators", []) or [])
    accelerating_count = sum(1 for item in indicators if str(_get(item, "trend_label", "")).lower() == "accelerating")
    spike_values = [_clip01(_get(item, "spike_severity", 0.0) / 5.0) or 0.6 for item in indicators if bool(_get(item, "is_spike", False))]
    trend_bonus = min(0.20, accelerating_count * 0.05 + len(spike_values) * 0.08)
    spike_bonus = min(0.15, len(spike_values) * 0.05)
    return round(trend_bonus, 4), round(spike_bonus, 4)


def build_escalation_input(state_context: Any, domains: SREDomains, projected: Sequence[ObservedSignal]) -> EscalationInput:
    base = _clip01(
        domains.capability * 0.35
        + domains.intent * 0.30
        + domains.stability * 0.20
        + domains.cost * 0.15
    )
    trend_bonus, spike_bonus = _temporal_bonuses(state_context)
    mobilization = any(
        item.signal_code == "MIL_MOBILIZATION" and not item.excluded_from_sre and item.membership >= 0.60 and item.confidence >= 0.25
        for item in projected
    )
    logistics = any(
        item.signal_code == "LOGISTICS_PREP" and not item.excluded_from_sre and item.membership >= 0.55 and item.confidence >= 0.22
        for item in projected
    )
    active_conflicts = [str(item) for item in list(_get(state_context, "active_conflicts", []) or []) if str(item)]
    return EscalationInput(
        base_score=round(base, 4),
        trend_bonus=trend_bonus,
        temporal_spike_bonus=spike_bonus,
        mobilization_trigger=mobilization,
        mobilization_bonus=0.10 if mobilization else 0.0,
        logistics_trigger=logistics,
        logistics_bonus=0.07 if logistics else 0.0,
        capability_floor_applied=domains.capability < 0.30,
        conflict_floor_applied=bool(active_conflicts),
        confidence_decay=_clip01(_get(state_context, "confidence_decay", 1.0), 1.0),
        active_conflicts=active_conflicts,
    )


def compute_escalation_index(domains: SREDomains, sre_input: EscalationInput) -> Tuple[float, str, List[Dict[str, Any]]]:
    trace: List[Dict[str, Any]] = [
        {"step": "domain_fusion", "score": sre_input.base_score, "domains": domains.model_dump(mode="json")},
    ]
    score = sre_input.base_score + sre_input.trend_bonus + sre_input.temporal_spike_bonus
    trace.append({"step": "temporal_bonus", "delta": round(sre_input.trend_bonus + sre_input.temporal_spike_bonus, 4), "score": round(score, 4)})
    if sre_input.capability_floor_applied:
        score *= 0.85
        trace.append({"step": "capability_floor", "delta": "x0.85", "score": round(score, 4)})
    if sre_input.mobilization_trigger:
        score += sre_input.mobilization_bonus
        trace.append({"step": "mobilization_trigger", "delta": sre_input.mobilization_bonus, "score": round(score, 4)})
    if sre_input.logistics_trigger:
        score += sre_input.logistics_bonus
        trace.append({"step": "logistics_trigger", "delta": sre_input.logistics_bonus, "score": round(score, 4)})
    if sre_input.conflict_floor_applied and score < 0.50:
        score = 0.50
        trace.append({"step": "active_conflict_floor", "floor": 0.50, "score": round(score, 4)})
    score = round(_clip01(score), 4)
    if score < 0.20:
        risk = "LOW"
    elif score < 0.40:
        risk = "MODERATE"
    elif score < 0.60:
        risk = "ELEVATED"
    elif score < 0.80:
        risk = "HIGH"
    else:
        risk = "CRITICAL"
    trace.append({"step": "risk_band", "risk_level": risk, "score": score})
    return score, risk, trace


class FuzzyStateInterpreter:
    @staticmethod
    def band(value: float) -> str:
        value = _clip01(value)
        if value < 0.25:
            return "minimal"
        if value < 0.50:
            return "watch"
        if value < 0.75:
            return "elevated"
        return "severe"

    def interpret(self, domains: SREDomains, score: float) -> Dict[str, str]:
        return {
            "capability": self.band(domains.capability),
            "intent": self.band(domains.intent),
            "stability": self.band(domains.stability),
            "cost": self.band(domains.cost),
            "escalation": self.band(score),
        }


def run_fuzzy_sre(state_context: Any) -> SREAssessment:
    projected = project_state_to_observed_signals(state_context)
    domains = compute_domain_fusion(projected)
    sre_input = build_escalation_input(state_context, domains, projected)
    score, risk, trace = compute_escalation_index(domains, sre_input)
    beliefs = build_signal_beliefs(state_context)
    rejections = [
        {"signal_code": item.signal_code, "reason": item.exclusion_reason or "excluded"}
        for item in projected
        if item.excluded_from_sre
    ]
    return SREAssessment(
        fuzzy_memberships={belief.signal_code: belief.fuzzy_memberships for belief in beliefs},
        signal_beliefs=beliefs,
        projected_signals=projected,
        sre_domains=domains,
        sre_input=sre_input,
        sre_escalation_score=score,
        risk_level=risk,
        qualitative_bands=FuzzyStateInterpreter().interpret(domains, score),
        escalation_trace=trace,
        legal_firewall_rejections=rejections,
    )
