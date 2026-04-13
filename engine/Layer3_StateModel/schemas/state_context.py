"""
Layer-3 -> Layer-4 state contract.
Interpretation-only context.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set
from engine.Layer3_StateModel.reliability.signal_belief import SignalBelief
from engine.Layer3_StateModel.strategic_constraints import StrategicConstraints
from Core.evidence.provenance_tracker import Evidence, ProvenanceTracker

def _clamp01(val): return max(0.0, min(1.0, float(val or 0.0)))
def _as_int(val): return int(float(val or 0.0))


def _to_evidence_dict(row: Any) -> Dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if isinstance(row, Evidence):
        return row.to_dict()
    to_dict = getattr(row, "to_dict", None)
    if callable(to_dict):
        try:
            payload = to_dict()
            if isinstance(payload, dict):
                return dict(payload)
        except Exception:
            pass
    return {
        "source": str(getattr(row, "source", getattr(row, "source_name", "unknown")) or "unknown"),
        "url": str(getattr(row, "url", "") or ""),
        "date": str(getattr(row, "date", getattr(row, "publication_date", "")) or ""),
        "publication_date": str(getattr(row, "date", getattr(row, "publication_date", "")) or ""),
        "excerpt": str(getattr(row, "excerpt", "") or ""),
        "reliability": _clamp01(getattr(row, "reliability", getattr(row, "confidence", 0.0))),
        "confidence": _clamp01(getattr(row, "reliability", getattr(row, "confidence", 0.0))),
    }

@dataclass
class ActorsContext:
    subject_country: str
    target_country: str

@dataclass
class MilitaryContext:
    mobilization_level: float
    clash_history: int
    exercises: int

@dataclass
class DiplomaticContext:
    hostility_tone: float
    negotiations: float
    alliances: float
    official_stance: str = "unknown"

@dataclass
class EconomicContext:
    sanctions: float
    trade_dependency: float
    economic_pressure: float

@dataclass
class DomesticContext:
    regime_stability: float
    unrest: float
    protests: float

@dataclass
class CapabilityIndicators:
    troop_mobilization: str = "none"
    logistics_activity: str = "none"
    supply_stockpiling: str = "none"
    cyber_activity: str = "none"
    evacuation_activity: str = "none"

@dataclass
class MetaContext:
    data_confidence: float = 0.5
    time_recency: float = 0.0
    source_count: int = 0
    signal_intensity: float = 0.0
    event_volatility: float = 0.0
    source_consistency: float = 0.5
    temporal_stability: float = 0.5


@dataclass
class TemporalContext:
    stability: float = 0.5
    volatility: float = 0.5


@dataclass
class ObservationQuality:
    """
    Distinguishes measured reality from fallback assumptions.
    """
    sensor_coverage: float = 0.0
    data_freshness: float = 0.0
    source_count: int = 0
    is_observed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_coverage": _clamp01(self.sensor_coverage),
            "data_freshness": _clamp01(self.data_freshness),
            "source_count": _as_int(self.source_count),
            "is_observed": bool(self.is_observed),
        }

    @classmethod
    def from_any(cls, value: Any) -> "ObservationQuality":
        if isinstance(value, ObservationQuality):
            return value
        payload = dict(value or {}) if isinstance(value, dict) else {}
        return cls(
            sensor_coverage=_clamp01(payload.get("sensor_coverage", 0.0)),
            data_freshness=_clamp01(payload.get("data_freshness", 0.0)),
            source_count=_as_int(payload.get("source_count", 0)),
            is_observed=bool(payload.get("is_observed", False)),
        )


@dataclass
class EvidenceContext:
    rag_documents: List[Any] = field(default_factory=list)
    rag_reasoning: str = ""
    rag_confidence: float = 0.0
    source_uris: List[str] = field(default_factory=list)
    signal_provenance: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

@dataclass
class StateContext:
    """
    Interpreted reality contract consumed by Layer-4.
    """
    actors: ActorsContext
    military: MilitaryContext
    diplomatic: DiplomaticContext
    economic: EconomicContext
    domestic: DomesticContext
    capability: CapabilityIndicators
    meta: MetaContext
    evidence: EvidenceContext = field(default_factory=EvidenceContext)
    temporal: TemporalContext = field(default_factory=TemporalContext)
    signal_beliefs: List[SignalBelief] = field(default_factory=list)
    observed_signals: Set[str] = field(default_factory=set)
    signal_confidence: Dict[str, float] = field(default_factory=dict)
    signal_evidence: Dict[str, List[Any]] = field(default_factory=dict)
    provenance: ProvenanceTracker = field(default_factory=ProvenanceTracker)
    constraints: StrategicConstraints = field(default_factory=StrategicConstraints)
    pressures: Dict[str, float] = field(default_factory=dict)
    observation_quality: ObservationQuality = field(default_factory=ObservationQuality)
    risk_level: str = "UNKNOWN"
    capability_index: float = 0.0
    intent_index: float = 0.0
    stability_index: float = 0.0
    cost_index: float = 0.0
    net_escalation: float = 0.0
    schema_version: str = "v1"

    # ── Temporal trend briefing (injected before council) ─────────
    # Dict of signal → {momentum, momentum_label, persistence,
    #                    persistence_label, spike, current_value}
    # Ministers read this to reason about *direction*, not just level.
    trend_briefing: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Summary flags for quick decision logic
    escalation_patterns: List[str] = field(default_factory=list)
    trend_snapshot_count: int = 0

    def summary(self) -> str:
        return (
            f"State({self.actors.subject_country}->{self.actors.target_country}) "
            f"Mil:{self.military.mobilization_level:.1f} "
            f"Dip:{self.diplomatic.hostility_tone:.1f}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actors": self.actors.__dict__,
            "military": self.military.__dict__,
            "diplomatic": self.diplomatic.__dict__,
            "economic": self.economic.__dict__,
            "domestic": self.domestic.__dict__,
            "capability": self.capability.__dict__,
            "meta": self.meta.__dict__,
            "evidence": self.evidence.__dict__,
            "temporal": self.temporal.__dict__,
            "signal_beliefs": [belief.__dict__ for belief in list(self.signal_beliefs or [])],
            "observed_signals": sorted(str(token) for token in set(self.observed_signals or set())),
            "signal_confidence": {
                str(key): _clamp01(value)
                for key, value in dict(self.signal_confidence or {}).items()
            },
            "signal_evidence": {
                str(key): [_to_evidence_dict(row) for row in list(value or [])]
                for key, value in dict(self.signal_evidence or {}).items()
            },
            "provenance": self.provenance.as_dict() if isinstance(self.provenance, ProvenanceTracker) else {},
            "constraints": (
                self.constraints.to_dict()
                if isinstance(self.constraints, StrategicConstraints)
                else StrategicConstraints.from_any(self.constraints).to_dict()
            ),
            "pressures": {
                str(key): _clamp01(value)
                for key, value in dict(self.pressures or {}).items()
            },
            "observation_quality": (
                self.observation_quality.to_dict()
                if isinstance(self.observation_quality, ObservationQuality)
                else ObservationQuality.from_any(self.observation_quality).to_dict()
            ),
            "risk_level": str(self.risk_level or "UNKNOWN"),
            "capability_index": _clamp01(self.capability_index),
            "intent_index": _clamp01(self.intent_index),
            "stability_index": _clamp01(self.stability_index),
            "cost_index": _clamp01(self.cost_index),
            "net_escalation": _clamp01(self.net_escalation),
        }

    # Helper for testing/mocking
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateContext":
        raw_beliefs = data.get("signal_beliefs", [])
        signal_beliefs: List[SignalBelief] = []
        if isinstance(raw_beliefs, list):
            for item in raw_beliefs:
                if isinstance(item, SignalBelief):
                    signal_beliefs.append(item)
                    continue
                if isinstance(item, dict):
                    try:
                        signal_beliefs.append(SignalBelief(**item))
                    except Exception:
                        continue
        raw_observed = data.get("observed_signals", [])
        observed_signals: Set[str] = set()
        if isinstance(raw_observed, (list, set, tuple)):
            for token in raw_observed:
                label = str(token or "").strip()
                if label:
                    observed_signals.add(label)

        raw_confidence = data.get("signal_confidence", {})
        signal_confidence: Dict[str, float] = {}
        if isinstance(raw_confidence, dict):
            for key, value in raw_confidence.items():
                token = str(key or "").strip()
                if not token:
                    continue
                signal_confidence[token] = _clamp01(value)

        raw_evidence = data.get("signal_evidence", {})
        signal_evidence: Dict[str, List[Any]] = {}
        if isinstance(raw_evidence, dict):
            for key, value in raw_evidence.items():
                token = str(key or "").strip()
                if not token:
                    continue
                if isinstance(value, list):
                    signal_evidence[token] = list(value)
                elif value is None:
                    signal_evidence[token] = []
                else:
                    signal_evidence[token] = [value]

        raw_provenance = data.get("provenance", {})
        if not isinstance(raw_provenance, dict):
            raw_provenance = {}
        if not raw_provenance:
            raw_evidence_ctx = data.get("evidence", {})
            if isinstance(raw_evidence_ctx, dict):
                maybe_signal_prov = raw_evidence_ctx.get("signal_provenance", {})
                if isinstance(maybe_signal_prov, dict):
                    raw_provenance = maybe_signal_prov
        provenance = ProvenanceTracker.from_dict(raw_provenance)

        raw_pressures = data.get("pressures", {})
        pressures: Dict[str, float] = {}
        if isinstance(raw_pressures, dict):
            for key, value in raw_pressures.items():
                token = str(key or "").strip()
                if not token:
                    continue
                pressures[token] = _clamp01(value)

        observation_quality = ObservationQuality.from_any(data.get("observation_quality", {}))
        constraints = StrategicConstraints.from_any(data.get("constraints", {}))

        # If explicit signal_evidence is missing, derive from provenance map.
        if not signal_evidence:
            signal_evidence = {
                str(signal): [Evidence.from_any(row).to_dict() for row in list(rows or [])]
                for signal, rows in list(provenance.export().items())
            }
        return cls(
            actors=ActorsContext(**data.get("actors", {})),
            military=MilitaryContext(**data.get("military", {})),
            diplomatic=DiplomaticContext(**data.get("diplomatic", {})),
            economic=EconomicContext(**data.get("economic", {})),
            domestic=DomesticContext(**data.get("domestic", {})),
            capability=CapabilityIndicators(**data.get("capability", {})),
            meta=MetaContext(**data.get("meta", {})),
            evidence=EvidenceContext(**data.get("evidence", {})),
            temporal=TemporalContext(**data.get("temporal", {})),
            signal_beliefs=signal_beliefs,
            observed_signals=observed_signals,
            signal_confidence=signal_confidence,
            signal_evidence=signal_evidence,
            provenance=provenance,
            constraints=constraints,
            pressures=pressures,
            observation_quality=observation_quality,
            risk_level=str(data.get("risk_level", "UNKNOWN") or "UNKNOWN"),
            capability_index=_clamp01(data.get("capability_index", 0.0)),
            intent_index=_clamp01(data.get("intent_index", 0.0)),
            stability_index=_clamp01(data.get("stability_index", 0.0)),
            cost_index=_clamp01(data.get("cost_index", 0.0)),
            net_escalation=_clamp01(data.get("net_escalation", 0.0)),
        )
