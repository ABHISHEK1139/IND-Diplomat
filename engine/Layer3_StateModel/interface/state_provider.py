"""
Single Layer-3 interface exposed to Layer-4.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

from engine.Layer3_StateModel.construction.analysis_readiness import (
    AnalysisReadinessReport,
    evaluate_analysis_readiness,
)
from engine.Layer3_StateModel.schemas.state_context import (
    StateContext, 
    MilitaryContext, 
    DiplomaticContext, 
    EconomicContext, 
    DomesticContext, 
    ActorsContext, 
    CapabilityIndicators, 

    MetaContext,
    EvidenceContext,
    TemporalContext,
    ObservationQuality,
)
from engine.Layer3_StateModel.temporal.precursor_monitor import PrecursorMonitor
from engine.Layer3_StateModel.construction.country_state_builder import CountryStateBuilder
from engine.Layer3_StateModel.reliability.signal_belief_model import SignalBeliefModel
from engine.Layer3_StateModel.strategic_constraints import compute_constraints
from engine.Layer3_StateModel.causal_signal_mapper import compute_escalation
from engine.Layer3_StateModel.temporal.state_history import save_state
from Core.evidence.provenance_tracker import Evidence, ProvenanceTracker
from Core.legal.legal_reasoner import LegalReasoner
from Core.economic.economic_reasoner import EconomicReasoner

try:
    from Core.legal.rag_bridge import (
        retrieve_legal_evidence,
        inject_legal_evidence_into_context,
    )
    _RAG_AVAILABLE = True
except ImportError:
    _RAG_AVAILABLE = False



_precursor_monitor = PrecursorMonitor()
_country_builder = CountryStateBuilder()
_signal_belief_model = SignalBeliefModel()
_legal_reasoner = LegalReasoner()
_economic_reasoner = EconomicReasoner()

_SOURCE_URLS: Dict[str, str] = {
    "GDELT": "https://www.gdeltproject.org/",
    "SIPRI": "https://www.sipri.org/",
    "WorldBank": "https://data.worldbank.org/",
    "Sanctions": "https://www.sanctionsmap.eu/",
    "OFAC": "https://ofac.treasury.gov/",
    "UCDP": "https://ucdp.uu.se/",
    "V-Dem": "https://www.v-dem.net/",
    "ATOP": "https://atopdata.org/",
    "EEZ": "https://www.marineregions.org/",
    "Comtrade": "https://comtradeplus.un.org/",
    "ComtradeProxy": "https://comtradeplus.un.org/",
    "DiplomacyIndex": "https://www.lowyinstitute.org/",
    "Leaders": "https://www.cia.gov/the-world-factbook/",
    "Ports": "https://www.worldportsource.com/",
}

_DIMENSION_SIGNAL_MAP: Dict[str, List[str]] = {
    "military": [
        "SIG_MIL_MOBILIZATION",
        "SIG_MIL_ESCALATION",
        "SIG_FORCE_CONCENTRATION",
        "SIG_FORCE_POSTURE",
        "SIG_LOGISTICS_SURGE",
        "SIG_LOGISTICS_PREP",
    ],
    "diplomatic": [
        "SIG_DIP_HOSTILITY",
        "SIG_DIP_HOSTILE_RHETORIC",
        "SIG_NEGOTIATION_BREAKDOWN",
        "SIG_ALLIANCE_SHIFT",
        "SIG_ALLIANCE_ACTIVATION",
    ],
    "economic": [
        "SIG_ECONOMIC_PRESSURE",
        "SIG_ECON_PRESSURE",
        "SIG_SANCTIONS_ACTIVE",
        "SIG_ECO_SANCTIONS_ACTIVE",
    ],
    "domestic": [
        "SIG_INTERNAL_INSTABILITY",
        "SIG_REGIME_STABLE",
        "SIG_DOM_INTERNAL_INSTABILITY",
    ],
    "conflict": [
        "SIG_MIL_ESCALATION",
        "SIG_FORCE_CONCENTRATION",
        "SIG_DIP_HOSTILITY",
    ],
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clip01(value: Any) -> float:
    return max(0.0, min(1.0, _safe_float(value, 0.0)))


def _excerpt(text: Any, limit: int = 240) -> str:
    raw = str(text or "").strip().replace("\n", " ")
    if len(raw) <= limit:
        return raw
    return raw[: max(1, limit - 3)] + "..."


def _normalize_date(value: Any, fallback: str = "") -> str:
    token = str(value or "").strip()
    return token if token else str(fallback or "")


def _source_to_observation_type(source_name: Any) -> str:
    source = str(source_name or "").lower()
    if any(k in source for k in ("gov", "official", "state.gov", "mod.", "ministry", "embassy")):
        return "GOV"
    if any(k in source for k in ("reuters", "ap", "bbc", "afp", "nyt", "news", "moltbot")):
        return "NEWS"
    if any(k in source for k in ("sipri", "gdelt", "worldbank", "ucdp", "dataset", "un")):
        return "DATASET"
    return "OSINT"


def _normalize_observation_timestamp(value: Any) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    if len(token) == 10 and token[4:5] == "-" and token[7:8] == "-":
        return f"{token}T12:00:00Z"
    return token


def _observation_from_signal_hit(hit: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_obs = hit.get("raw_observation")
    if isinstance(raw_obs, dict) and str(raw_obs.get("signal", "") or "").strip():
        return dict(raw_obs)

    signal = str(hit.get("signal", "") or "").strip().upper()
    if not signal:
        return None

    timestamp = _normalize_observation_timestamp(hit.get("publication_date"))
    source_type = _source_to_observation_type(hit.get("source", ""))
    excerpt = _excerpt(hit.get("excerpt", ""), limit=320)
    source_id = str(hit.get("source_id") or f"signal_hit_{signal}_{hash((excerpt, hit.get('url', ''))) % 100000}")

    return {
        "type": "observation",
        "signal": signal,
        "source_type": source_type,
        "evidence_strength": max(0.35, min(0.75, _clip01(hit.get("score", 0.45)))),
        "corroboration": 1,
        "keyword_hits": 1,
        "origin_id": source_id,
        "source": str(hit.get("source") or source_type),
        "url": str(hit.get("url") or ""),
        "timestamp": timestamp,
        "crawl_timestamp": "",
        "date_source": str(hit.get("date_source") or ("signal_hit" if timestamp else "unknown")),
        "date_confidence": 0.75 if timestamp else 0.20,
        "event_confidence": 0.60,
        "excerpt": excerpt,
    }


def _compute_observation_quality(
    *,
    vector: Any,
    rag_documents: Optional[List[Dict[str, Any]]] = None,
) -> ObservationQuality:
    """
    Observation quality is authority metadata:
    did we observe the world, or are we relying on fallback priors?
    """
    # Primary authority: observation metadata emitted by CountryStateBuilder.
    signal_breakdown = getattr(vector, "signal_breakdown", {}) or {}
    observation_meta = signal_breakdown.get("observation_quality", {}) if isinstance(signal_breakdown, dict) else {}

    if isinstance(observation_meta, dict):
        source_count = int(
            max(
                0,
                _safe_float(
                    observation_meta.get(
                        "validated_source_count",
                        observation_meta.get("primary_sensor_records", 0),
                    ),
                    0,
                ),
            )
        )
        available_sources = int(
            max(
                1,
                _safe_float(observation_meta.get("available_source_count", source_count or 1), 1),
            )
        )
        sensor_coverage = max(0.0, min(1.0, _safe_float(observation_meta.get("sensor_coverage", 0.0), 0.0)))
        if sensor_coverage <= 0.0 and available_sources > 0:
            sensor_coverage = max(0.0, min(1.0, source_count / float(available_sources)))
        is_observed = bool(observation_meta.get("is_observed", source_count > 0))
    else:
        source_count = int(max(0, _safe_float(getattr(vector, "recent_activity_signals", 0), 0)))
        provider_health = signal_breakdown.get("provider_health", {}) if isinstance(signal_breakdown, dict) else {}
        available_sources = len(provider_health) if isinstance(provider_health, dict) and provider_health else max(1, source_count)
        sensor_coverage = max(0.0, min(1.0, float(source_count) / float(max(1, available_sources))))
        is_observed = bool(source_count > 0)

    # Freshness reflects whether those observed records were recent.
    data_freshness = 1.0 if source_count > 0 else 0.0

    # Optional freshness hint from vector payload if present.
    freshness_map = getattr(vector, "data_freshness", {}) or {}
    if isinstance(freshness_map, dict) and freshness_map:
        dated = 0
        for value in freshness_map.values():
            token = str(value or "").strip().upper()
            if token and token != "N/A":
                dated += 1
        if len(freshness_map) > 0:
            data_freshness = max(data_freshness, max(0.0, min(1.0, dated / len(freshness_map))))

    quality = ObservationQuality(
        sensor_coverage=sensor_coverage,
        data_freshness=data_freshness,
        source_count=source_count,
        is_observed=bool(is_observed),
    )
    return quality


def _source_url(source_name: Any) -> str:
    name = str(source_name or "").strip()
    return _SOURCE_URLS.get(name, "")


def _build_dimension_evidence(
    *,
    country_code: str,
    assessment_date: str,
    dimension_name: str,
    score_obj: Any,
) -> List[Evidence]:
    sources = list(getattr(score_obj, "contributing_sources", []) or [])
    if not sources:
        sources = ["Layer3StateModel"]

    explanation = _excerpt(
        getattr(score_obj, "explanation", "")
        or f"{dimension_name} score={_safe_float(getattr(score_obj, 'value', 0.0), 0.0):.2f}"
    )
    confidence = _clip01(getattr(score_obj, "confidence", 0.5))
    publication_date = _normalize_date(
        getattr(score_obj, "last_data_date", ""),
        fallback=assessment_date,
    )

    evidence_rows: List[Evidence] = []
    for index, source_name in enumerate(sources):
        source = str(source_name or "unknown")
        evidence_rows.append(
            Evidence(
                source=source,
                url=_source_url(source),
                date=publication_date,
                excerpt=explanation,
                reliability=confidence,
                source_id=f"{country_code}_{dimension_name}_{index}_{publication_date}",
            )
        )
    return evidence_rows


def _attach_dimension_provenance(
    tracker: ProvenanceTracker,
    *,
    dimension_name: str,
    evidences: Iterable[Evidence],
) -> None:
    signals = list(_DIMENSION_SIGNAL_MAP.get(dimension_name, []) or [])
    if not signals:
        return
    rows = list(evidences or [])
    for signal in signals:
        tracker.extend(signal, rows)


def _infer_signals_from_text(text: str) -> List[str]:
    token = str(text or "").lower()
    inferred: List[str] = []
    if any(word in token for word in ("troop", "military", "exercise", "mobilization", "border", "logistics")):
        inferred.extend(["SIG_MIL_ESCALATION", "SIG_MIL_MOBILIZATION", "SIG_FORCE_POSTURE"])
    if any(word in token for word in ("sanction", "trade", "tariff", "econom")):
        inferred.extend(["SIG_ECON_PRESSURE", "SIG_ECONOMIC_PRESSURE", "SIG_SANCTIONS_ACTIVE"])
    if any(word in token for word in ("statement", "diplomatic", "minister", "alliance", "negotiat", "rhetoric")):
        inferred.extend(["SIG_DIP_HOSTILITY", "SIG_NEGOTIATION_BREAKDOWN", "SIG_ALLIANCE_SHIFT"])
    if any(word in token for word in ("protest", "unrest", "regime", "domestic")):
        inferred.extend(["SIG_INTERNAL_INSTABILITY", "SIG_REGIME_STABLE"])
    if not inferred:
        inferred.extend(["SIG_MIL_ESCALATION", "SIG_DIP_HOSTILITY", "SIG_ECON_PRESSURE"])
    # preserve order while deduping
    seen = set()
    ordered: List[str] = []
    for item in inferred:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _apply_legal_reasoning(
    state_context: StateContext,
    *,
    assessment_date: str = "",
) -> List[str]:
    observed = {
        str(token or "").strip().upper()
        for token in list(getattr(state_context, "observed_signals", set()) or set())
        if str(token or "").strip()
    }
    legal_flags = sorted(_legal_reasoner.evaluate(observed))
    if not legal_flags:
        return []

    confidence_map = dict(getattr(state_context, "signal_confidence", {}) or {})
    signal_evidence = dict(getattr(state_context, "signal_evidence", {}) or {})
    provenance_map = dict(getattr(state_context.evidence, "signal_provenance", {}) or {})

    for legal_signal in legal_flags:
        supports = _legal_reasoner.supporting_observed_signals(legal_signal, observed)
        support_scores = [
            _clip01(confidence_map.get(sig, 0.0))
            for sig in list(supports or [])
            if sig in confidence_map
        ]
        legal_conf = _clip01(max(support_scores) if support_scores else 0.55)
        state_context.observed_signals.add(legal_signal)
        state_context.signal_confidence[legal_signal] = max(
            _clip01(state_context.signal_confidence.get(legal_signal, 0.0)),
            legal_conf,
        )

        support_text = ", ".join(list(supports or [])) if supports else "none"
        row = {
            "source_id": f"legal_reasoner::{legal_signal}::{assessment_date or 'na'}",
            "source": "LegalReasoner",
            "source_name": "LegalReasoner",
            "url": "",
            "publication_date": str(assessment_date or ""),
            "date": str(assessment_date or ""),
            "excerpt": (
                f"Derived legal flag {legal_signal} from observed signals: {support_text}."
            ),
            "confidence": float(legal_conf),
            "reliability": float(legal_conf),
        }
        key = (
            str(row.get("source_id", "")),
            str(row.get("publication_date", "")),
            str(row.get("url", "")),
            str(row.get("excerpt", "")),
        )

        sig_rows = list(signal_evidence.get(legal_signal, []) or [])
        sig_keys = {
            (
                str(item.get("source_id", "")),
                str(item.get("publication_date", "")),
                str(item.get("url", "")),
                str(item.get("excerpt", "")),
            )
            for item in sig_rows
            if isinstance(item, dict)
        }
        if key not in sig_keys:
            sig_rows.append(dict(row))
        signal_evidence[legal_signal] = sig_rows

        prov_rows = list(provenance_map.get(legal_signal, []) or [])
        prov_keys = {
            (
                str(item.get("source_id", "")),
                str(item.get("publication_date", "")),
                str(item.get("url", "")),
                str(item.get("excerpt", "")),
            )
            for item in prov_rows
            if isinstance(item, dict)
        }
        if key not in prov_keys:
            prov_rows.append(dict(row))
        provenance_map[legal_signal] = prov_rows

    state_context.signal_evidence = signal_evidence
    state_context.evidence.signal_provenance = provenance_map
    return legal_flags


def _apply_economic_reasoning(
    state_context: StateContext,
    *,
    assessment_date: str = "",
) -> List[str]:
    def _coerce_row(row: Any) -> Optional[Dict[str, Any]]:
        if isinstance(row, dict):
            return dict(row)
        to_dict = getattr(row, "to_dict", None)
        if callable(to_dict):
            try:
                payload = to_dict()
                if isinstance(payload, dict):
                    return dict(payload)
            except Exception:
                return None
        return None

    def _row_key(row: Dict[str, Any]) -> Tuple[str, str, str, str]:
        return (
            str(row.get("source_id", "")),
            str(row.get("publication_date", row.get("date", ""))),
            str(row.get("url", "")),
            str(row.get("excerpt", row.get("content", ""))),
        )

    signal_evidence = dict(getattr(state_context, "signal_evidence", {}) or {})
    provenance_map = dict(getattr(state_context.evidence, "signal_provenance", {}) or {})
    confidence_map = dict(getattr(state_context, "signal_confidence", {}) or {})

    has_comtrade_evidence = bool(signal_evidence.get("SIG_ECO_TRADE_LEVERAGE")) or bool(
        provenance_map.get("SIG_ECO_TRADE_LEVERAGE")
    )
    economic_flags = sorted(
        _economic_reasoner.evaluate(
            state_context,
            has_comtrade_evidence=has_comtrade_evidence,
        )
    )
    if not economic_flags:
        return []

    support_key_map: Dict[str, List[str]] = {
        "SIG_ECO_SANCTIONS_ACTIVE": [
            "SIG_ECO_SANCTIONS_ACTIVE",
            "SIG_SANCTIONS_ACTIVE",
        ],
        "SIG_ECO_PRESSURE_HIGH": [
            "SIG_ECO_PRESSURE_HIGH",
            "SIG_ECONOMIC_PRESSURE",
            "SIG_ECON_PRESSURE",
        ],
        "SIG_ECONOMIC_PRESSURE": [
            "SIG_ECONOMIC_PRESSURE",
            "SIG_ECON_PRESSURE",
            "SIG_ECO_PRESSURE_HIGH",
            "SIG_ECO_SANCTIONS_ACTIVE",
            "SIG_SANCTIONS_ACTIVE",
        ],
        "SIG_ECO_TRADE_LEVERAGE": [
            "SIG_ECO_TRADE_LEVERAGE",
        ],
    }

    metrics = _economic_reasoner.supporting_metrics(state_context)
    for economic_signal in economic_flags:
        support_keys = list(support_key_map.get(economic_signal, [economic_signal]))
        support_rows: List[Dict[str, Any]] = []
        seen_support = set()

        for key in support_keys:
            for row in list(signal_evidence.get(key, []) or []):
                payload = _coerce_row(row)
                if not payload:
                    continue
                rkey = _row_key(payload)
                if rkey in seen_support:
                    continue
                seen_support.add(rkey)
                support_rows.append(payload)

            for row in list(provenance_map.get(key, []) or []):
                payload = _coerce_row(row)
                if not payload:
                    continue
                rkey = _row_key(payload)
                if rkey in seen_support:
                    continue
                seen_support.add(rkey)
                support_rows.append(payload)

        reliabilities = []
        for row in support_rows:
            reliabilities.append(
                _clip01(row.get("reliability", row.get("confidence", 0.0)))
            )
        economic_conf = _clip01(
            (sum(reliabilities) / len(reliabilities)) if reliabilities else 0.55
        )

        state_context.observed_signals.add(economic_signal)
        state_context.signal_confidence[economic_signal] = max(
            _clip01(state_context.signal_confidence.get(economic_signal, 0.0)),
            economic_conf,
        )

        support_text = ", ".join(list(support_keys or [])) if support_keys else "none"
        explanation_row = {
            "source_id": f"economic_reasoner::{economic_signal}::{assessment_date or 'na'}",
            "source": "EconomicReasoner",
            "source_name": "EconomicReasoner",
            "url": "",
            "publication_date": str(assessment_date or ""),
            "date": str(assessment_date or ""),
            "excerpt": (
                f"Derived economic flag {economic_signal} from metrics "
                f"sanctions={metrics.get('sanctions', 0.0):.3f}, "
                f"economic_pressure={metrics.get('economic_pressure', 0.0):.3f}, "
                f"trade_dependency={metrics.get('trade_dependency', 0.0):.3f}; "
                f"support_keys={support_text}."
            ),
            "confidence": float(economic_conf),
            "reliability": float(economic_conf),
        }

        sig_rows = list(signal_evidence.get(economic_signal, []) or [])
        sig_keys = {
            _row_key(payload)
            for payload in [
                _coerce_row(item) for item in sig_rows
            ]
            if isinstance(payload, dict)
        }
        for row in list(support_rows) + [explanation_row]:
            rkey = _row_key(row)
            if rkey in sig_keys:
                continue
            sig_keys.add(rkey)
            sig_rows.append(dict(row))
        signal_evidence[economic_signal] = sig_rows

        prov_rows = list(provenance_map.get(economic_signal, []) or [])
        prov_keys = {
            _row_key(payload)
            for payload in [
                _coerce_row(item) for item in prov_rows
            ]
            if isinstance(payload, dict)
        }
        for row in list(support_rows) + [explanation_row]:
            rkey = _row_key(row)
            if rkey in prov_keys:
                continue
            prov_keys.add(rkey)
            prov_rows.append(dict(row))
        provenance_map[economic_signal] = prov_rows

    state_context.signal_evidence = signal_evidence
    state_context.evidence.signal_provenance = provenance_map
    state_context.signal_confidence = confidence_map | dict(state_context.signal_confidence or {})
    return economic_flags


def get_state_context(
    question: str,
    *,
    state_context: Optional[Dict[str, Any]] = None,
    country_state: Any = None,
    relationship_state: Any = None,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> StateContext:
    """
    Build/normalize StateContext for Layer-4 from Layer-3 outputs.
    """
    _ = question
    rows = list(sources or [])
    if state_context:
        return StateContext.from_any(
            state_context,
            country_state=country_state,
            relationship_state=relationship_state,
            sources=rows,
        )
    return StateContext.from_layer3(
        country_state=country_state,
        relationship_state=relationship_state,
        sources=rows,
    )


def get_state_context_dict(
    question: str,
    *,
    state_context: Optional[Dict[str, Any]] = None,
    country_state: Any = None,
    relationship_state: Any = None,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return get_state_context(
        question,
        state_context=state_context,
        country_state=country_state,
        relationship_state=relationship_state,
        sources=sources,
    ).to_dict()


def evaluate_precursors(state_context: Dict[str, Any] | Any) -> Dict[str, Any]:
    return _precursor_monitor.evaluate(state_context)


def get_analysis_readiness(
    *,
    country_state: Any,
    relationship_state: Any = None,
    confidence: float | None = None,
) -> AnalysisReadinessReport:
    return evaluate_analysis_readiness(
        country_state=country_state,
        relationship_state=relationship_state,
        confidence=confidence,
    )


def build_initial_state(query: str, country_code: str = "UNKNOWN", as_of_date: Optional[str] = None) -> StateContext:
    """
    Build the initial StateContext for a query by constructing the Layer-3 Vector
    and mapping it to the Layer-4 Interpreted Context.
    """
    # 1. Build Country State (Layer 3) - Uses Sensors (GDELT, WorldBank, etc.)
    vector = _country_builder.build(country_code=country_code, date=as_of_date)

    # 2. Map Vector to Context (Layer 4 Contract)
    # Heuristic mapping until more granular sensors are available
    
    # Military
    mil_ctx = MilitaryContext(
        mobilization_level=vector.military_pressure.value,
        clash_history=int(vector.conflict_activity.value * 10), # Scale to count
        exercises=int(vector.military_pressure.value * 5) # Heuristic
    )
    
    # Diplomatic
    dip_ctx = DiplomaticContext(
        hostility_tone=vector.diplomatic_isolation.value,
        negotiations=(1.0 - vector.diplomatic_isolation.value), # Inverse of isolation
        alliances=0.5 # Default/Unknown
    )
    
    # Economic
    eco_ctx = EconomicContext(
        sanctions=vector.economic_stress.value,
        trade_dependency=0.5, # Placeholder
        economic_pressure=vector.economic_stress.value
    )
    
    # Domestic
    # Internal stability low = High unrest
    unrest = max(0.0, 1.0 - vector.internal_stability.value)
    dom_ctx = DomesticContext(
        unrest=unrest,
        regime_stability=vector.internal_stability.value,
        protests=unrest  # Normalized 0.0-1.0 to match evidence_tracker expectations
    )
    
    # Actors (Derived from query/code)
    # Ideally should parse query for target. Defaulting for now.
    actors = ActorsContext(
        subject_country=country_code,
        target_country="UNKNOWN" 
    )
    
    # Capability
    cap = CapabilityIndicators(
        troop_mobilization="high" if vector.military_pressure.value > 0.6 else "low",
        logistics_activity="normal",
        supply_stockpiling="none",
        cyber_activity="low",
        evacuation_activity="none"
    )

    # Meta
    data_confidence = _clip01(
        vector.signal_breakdown.get("validation_confidence", {}).get("score", 0.5)
    )
    temporal_stability = _clip01(getattr(vector, "stability_index", 0.5))
    signal_breakdown = getattr(vector, "signal_breakdown", {}) or {}
    observation_meta = (
        signal_breakdown.get("observation_quality", {})
        if isinstance(signal_breakdown, dict)
        else {}
    )
    source_count = int(
        _safe_float(
            observation_meta.get(
                "primary_sensor_records",
                getattr(vector, "recent_activity_signals", 0),
            ),
            0,
        )
    )
    meta = MetaContext(
        data_confidence=data_confidence,
        time_recency=1.0,  # Fresh build
        source_count=max(0, source_count),
        signal_intensity=_clip01(getattr(vector, "tension_index", 0.0)),
        event_volatility=_clip01(1.0 - temporal_stability),
        source_consistency=data_confidence,
        temporal_stability=temporal_stability,
    )

    temporal = TemporalContext(
        stability=temporal_stability,
        volatility=_clip01(getattr(vector, "escalation_risk", 0.0)),
    )

    # Evidence (RAG Routing Metadata â€” NOT raw document content)
    # BUG-01 FIX: Layer-4 must NEVER see raw document text.
    # We store only metadata about the evidence retrieval for traceability.
    tracker = ProvenanceTracker()
    assessment_date = _normalize_date(getattr(vector, "date", ""), fallback="")

    dimension_scores = {
        "military": vector.military_pressure,
        "diplomatic": vector.diplomatic_isolation,
        "economic": vector.economic_stress,
        "domestic": vector.internal_stability,
        "conflict": vector.conflict_activity,
    }
    for dimension_name, score_obj in list(dimension_scores.items()):
        rows = _build_dimension_evidence(
            country_code=str(country_code or "UNKNOWN"),
            assessment_date=assessment_date,
            dimension_name=dimension_name,
            score_obj=score_obj,
        )
        _attach_dimension_provenance(
            tracker,
            dimension_name=dimension_name,
            evidences=rows,
        )

    rag_source_count = 0
    rag_reasoning = ""
    rag_documents: List[Dict[str, Any]] = []
    source_uris: List[str] = []

    trigger_words = {
        "why", "explain", "treaty", "agreement", "reason", "history", "context", "detail",
        "impact", "affect", "how", "relations", "situation", "conflict", "dispute"
    }
    is_semantic = any(w in query.lower() for w in trigger_words)

    if is_semantic:
        try:
            from engine.Layer2_Knowledge.retriever import DiplomaticRetriever
            from engine.Layer2_Knowledge.event_ingestor import ingest_documents
            retriever = DiplomaticRetriever()
            results = retriever.hybrid_search(query, top_k=3)
            signal_hits = ingest_documents(list(results or []))
            rag_source_count = len(signal_hits)
            rag_reasoning = (
                "Routed to retrieval due to semantic keywords. "
                f"Fetched {len(list(results or []))} docs, extracted {rag_source_count} signal hits."
            )

            for hit in list(signal_hits or []):
                signal = str(hit.get("signal", "") or "").strip().upper()
                if not signal:
                    continue
                source_name = str(hit.get("source") or "Layer2Retriever")
                source_id = str(hit.get("source_id") or f"rag_{country_code}_{signal}")
                publication_date = _normalize_date(hit.get("publication_date"), fallback=assessment_date)
                url = str(hit.get("url") or "")
                score = _clip01(hit.get("score", 0.5))
                excerpt = _excerpt(hit.get("excerpt", ""))

                rag_documents.append(
                    {
                        "id": source_id,
                        "source": source_name,
                        "url": url,
                        "publication_date": publication_date,
                        "content": excerpt,
                        "score": score,
                        "signal": signal,
                    }
                )
                if url:
                    source_uris.append(url)

                evidence_item = Evidence(
                    source=source_name,
                    url=url,
                    date=publication_date,
                    excerpt=excerpt,
                    reliability=score,
                    source_id=source_id,
                )
                tracker.attach(signal, evidence_item)
        except ImportError:
            rag_reasoning = "RAG unavailable (ImportError)"
        except Exception as e:
            rag_reasoning = f"RAG failed: {e}"
    else:
        rag_reasoning = "No semantic trigger words detected. RAG skipped."

    rag_confidence = 0.0
    if rag_documents:
        rag_confidence = sum(_clip01(item.get("score", 0.0)) for item in rag_documents) / len(rag_documents)

    evidence = EvidenceContext(
        rag_documents=rag_documents,
        rag_reasoning=rag_reasoning,
        rag_confidence=rag_confidence,
        source_uris=sorted(set(source_uris)),
        signal_provenance=tracker.as_dict(),
    )

    state_context = StateContext(
        actors=actors,
        military=mil_ctx,
        diplomatic=dip_ctx,
        economic=eco_ctx,
        domestic=dom_ctx,
        capability=cap,
        meta=meta,
        evidence=evidence,
        temporal=temporal,
    )
    vector_breakdown = getattr(vector, "signal_breakdown", {}) or {}
    causal_dims = (
        vector_breakdown.get("causal_dimensions", {})
        if isinstance(vector_breakdown, dict)
        else {}
    )
    capability_index = _clip01(causal_dims.get("capability_index", vector.military_pressure.value))
    intent_index = _clip01(causal_dims.get("intent_index", vector.diplomatic_isolation.value))
    stability_index = _clip01(causal_dims.get("stability_index", 1.0 - vector.internal_stability.value))
    cost_index = _clip01(causal_dims.get("cost_index", vector.economic_stress.value))
    causal_decision = compute_escalation(
        capability_index,
        intent_index,
        stability_index,
        cost_index,
    )
    risk_token = str(
        getattr(getattr(vector, "overall_risk_level", None), "value", "")
        or causal_decision.get("risk_level", "LOW")
    ).strip().upper()
    state_context.risk_level = risk_token or "LOW"
    state_context.capability_index = capability_index
    state_context.intent_index = intent_index
    state_context.stability_index = stability_index
    state_context.cost_index = cost_index
    state_context.net_escalation = _clip01(causal_decision.get("net", 0.0))
    state_context.provenance = tracker
    state_context.constraints = compute_constraints(state_context)
    state_context.observation_quality = _compute_observation_quality(
        vector=vector,
        rag_documents=rag_documents,
    )
    state_context.signal_beliefs = _signal_belief_model.build_all(state_context)
    state_context.observed_signals = set()
    state_context.signal_confidence = {}
    state_context.signal_evidence = {}
    allow_observed_signals = bool(getattr(state_context.observation_quality, "is_observed", False))

    provenance_dict = dict(getattr(state_context.evidence, "signal_provenance", {}) or {})
    for belief in list(state_context.signal_beliefs or []):
        signal = str(getattr(belief, "signal", "") or "").strip().upper()
        if not signal:
            continue

        score = getattr(belief, "confidence", None)
        if score is None:
            score = getattr(belief, "belief", 0.0)
        score = _clip01(score)

        if allow_observed_signals and score >= 0.5:
            state_context.observed_signals.add(signal)
            state_context.signal_confidence[signal] = score
            if signal not in state_context.signal_evidence:
                tracked_rows = [
                    item.to_dict()
                    for item in list(state_context.provenance.get(signal) or [])
                ]
                if not tracked_rows:
                    tracked_rows = list(provenance_dict.get(signal, []) or [])
                state_context.signal_evidence[signal] = tracked_rows

    # ── Legal Module Gate ──────────────────────────────────────────
    from Config.config import ENABLE_LEGAL_MODULE as _LEGAL_ON
    if _LEGAL_ON:
        legal_flags = _apply_legal_reasoning(
            state_context,
            assessment_date=assessment_date,
        )
        print("LEGAL FLAGS:", legal_flags)
    else:
        legal_flags = []
        logger.info("[LEGAL] Module disabled (ENABLE_LEGAL_MODULE=false) — no legal signals injected")
        print("LEGAL FLAGS: [] (module disabled)")

    # ── RAG: DEFERRED TO POST-GATE (Pipeline Firewall) ─────────────
    # Legal/normative evidence is architecturally isolated from the
    # empirical analysis pipeline.  RAG retrieval now runs in the
    # coordinator AFTER the gate decision so that council, SRE, and
    # the gate never see legal corpus data.
    print("RAG EVIDENCE: deferred to post-gate (pipeline firewall)")

    economic_flags = _apply_economic_reasoning(
        state_context,
        assessment_date=assessment_date,
    )
    print("ECONOMIC FLAGS:", economic_flags)

    # ── Warm start from persisted temporal memory ────────────────
    # Load belief history from previous runs so the system doesn't
    # start from scratch each time.  Fresh sensor data (GDELT/MoltBot)
    # will overwrite/update these, but prior knowledge is preserved
    # if a sensor is temporarily unavailable.
    try:
        from engine.Layer3_StateModel.temporal_memory import warm_start_beliefs

        prior_beliefs = warm_start_beliefs(max_age_hours=48.0)
        if prior_beliefs:
            for sig, conf in prior_beliefs.items():
                sig = sig.strip().upper()
                if sig and conf >= 0.30:
                    state_context.observed_signals.add(sig)
                    # Only seed if not already set by the vector build
                    if sig not in state_context.signal_confidence:
                        state_context.signal_confidence[sig] = conf
            logger.info(
                "[build_initial_state] Warm start: %d prior beliefs loaded from history",
                len(prior_beliefs),
            )
    except ImportError:
        pass
    except Exception as _ws_err:
        logger.debug("Warm start skipped: %s", _ws_err)

    # ── GDELT live event perception ─────────────────────────────────
    # The GDELT sensor converts structured event records into
    # observations that the BeliefAccumulator can evaluate.
    # This gives the initial state live behavioral intelligence
    # (protests, threats, assaults) BEFORE the council convenes.
    try:
        from engine.Layer1_Collection.sensors.gdelt_sensor import sense_gdelt
        from engine.Layer3_StateModel.belief_accumulator import (
            BeliefAccumulator, apply_beliefs_to_state,
        )

        gdelt_obs = sense_gdelt(
            countries=[str(country_code or "UNKNOWN").upper()],
            hours_back=24,
        )
        if gdelt_obs:
            acc = BeliefAccumulator()
            gdelt_beliefs = acc.evaluate(gdelt_obs)
            if gdelt_beliefs:
                apply_beliefs_to_state(state_context, gdelt_beliefs)
                logger.info(
                    "[build_initial_state] GDELT sensor: %d obs → %d beliefs promoted",
                    len(gdelt_obs), len(gdelt_beliefs),
                )
    except ImportError as _ge:
        logger.debug("GDELT sensor adapter unavailable: %s", _ge)
    except Exception as _ge:
        logger.debug("GDELT sensor pass skipped: %s", _ge)

    # ── MoltBot OSINT narrative perception ──────────────────────────
    # The MoltBot sensor searches the open web for narrative articles,
    # extracts signal patterns via regex, and produces observations in
    # the SAME format as GDELT.  This runs BEFORE the council convenes
    # so that the state model includes both structured events (GDELT)
    # and narrative evidence (MoltBot).
    #
    # Cooldown-protected: at most one sweep per country per 15 min.
    try:
        from engine.Layer1_Sensors.moltbot_sensor import collect_country_osint
        from engine.Layer3_StateModel.belief_accumulator import (
            BeliefAccumulator as _MBAcc,
            apply_beliefs_to_state as _mb_apply,
        )

        moltbot_obs = collect_country_osint(
            str(country_code or "UNKNOWN").upper()
        )
        if moltbot_obs:
            mb_acc = _MBAcc()
            mb_beliefs = mb_acc.evaluate(moltbot_obs)
            if mb_beliefs:
                _mb_apply(state_context, mb_beliefs)
                logger.info(
                    "[build_initial_state] MoltBot sensor: %d obs → %d beliefs promoted",
                    len(moltbot_obs), len(mb_beliefs),
                )
    except ImportError as _me:
        logger.debug("MoltBot sensor adapter unavailable: %s", _me)
    except Exception as _me:
        logger.debug("MoltBot sensor pass skipped: %s", _me)

    # Temporal memory for early-warning trend analysis.
    # Best-effort only; temporal persistence must never block analytical runtime.
    try:
        save_state(str(country_code or "UNKNOWN"), state_context)
    except Exception:
        pass

    return state_context


def investigate_and_update(
    query: str,
    current_state: Dict[str, Any],
    investigation_needs: Dict[str, Any]
) -> Tuple[StateContext, List[str]]:
    """
    PIR-driven investigation update.

    Receives a typed collection plan (PIRs with closed modalities)
    from Layer-4.  Extracts the targeted signals from PIRs,
    rebuilds state context focused on those signals, and feeds
    any evidence found back into the new state.

    NEVER generates free-text search queries — all investigation is
    guided by typed PIR signals and collection modalities.
    """
    country = (
        current_state.get("actors", {}).get("subject_country")
        or current_state.get("country")
        or current_state.get("country_code")
        or current_state.get("meta", {}).get("country_code")
        or "UNKNOWN"
    )
    missing = investigation_needs.get("missing_signals", [])

    # ── Extract targeted signals from typed PIRs ──────────────────────
    # The coordinator passes a CollectionPlan with typed PIRs.
    # Each PIR specifies: signal, collection modality, priority, reason.
    # We extract the signal tokens to focus the state rebuild.
    pirs = investigation_needs.get("pirs", [])
    collection_plan = investigation_needs.get("collection_plan", {})

    targeted_signals: List[str] = []
    for pir_dict in pirs:
        sig = str(pir_dict.get("signal", "")).strip().upper()
        if sig and sig not in targeted_signals:
            targeted_signals.append(sig)

    # If PIRs are empty, fall back to missing signals from session.
    if not targeted_signals:
        targeted_signals = [
            str(token or "").strip().upper()
            for token in list(missing or [])
            if str(token or "").strip()
        ]

    if targeted_signals:
        logger.info(
            "[investigate_and_update] Targeting %d signals from PIRs: %s",
            len(targeted_signals),
            targeted_signals[:5],
        )
    else:
        logger.info("[investigate_and_update] No targeted signals — raw query rebuild only")

    new_observations: List[str] = []
    signal_hits: List[Dict[str, Any]] = []

    # ── PIR-driven collection via MoltBot bridge ────────────────────
    # The collection bridge converts typed PIRs into MoltBot tasks,
    # executes web collection, and returns signal_hits in the format
    # the evidence integrator below expects.
    #
    # MoltBot receives TOPICS (from modality→keyword map), NOT the
    # user's question.  It searches the world, not the query.
    #
    # If MoltBot is unavailable or returns nothing, the state rebuild
    # still proceeds from existing RAG data — this is best-effort.
    try:
        from Core.intelligence.collection_bridge import execute_collection_plan

        signal_hits = execute_collection_plan(
            pir_dicts=pirs,
            country=country,
            limit_per_pir=5,
            max_total_docs=25,
        )

        for hit in list(signal_hits or []):
            signal = str(hit.get("signal", "") or "").strip().upper()
            if signal and signal not in new_observations:
                new_observations.append(signal)

        if signal_hits:
            logger.info(
                "[investigate_and_update] MoltBot collection returned %d signal_hits",
                len(signal_hits),
            )

    except ImportError as e:
        logger.warning("[investigate_and_update] Collection bridge unavailable: %s", e)
    except Exception as e:
        logger.warning("[investigate_and_update] Collection bridge error: %s", e)

    # ── World Monitor fallback: use cached observations ───────────
    # When MoltBot and live GDELT both fail (e.g., no internet),
    # the World Monitor may have cached state from a previous sweep.
    # Inject any cached signals that match targeted PIRs.
    if not signal_hits:
        try:
            from runtime.world_monitor import get_prebuilt_state

            prebuilt = get_prebuilt_state(country)
            if prebuilt and isinstance(prebuilt, dict):
                cached_signals = prebuilt.get("signals", [])
                for sig in cached_signals:
                    sig = str(sig).strip().upper()
                    if sig in targeted_signals or not targeted_signals:
                        signal_hits.append({
                            "signal": sig,
                            "score": 0.50,  # lower confidence for cached data
                            "source": "WORLD_MONITOR_CACHE",
                            "url": "",
                            "publication_date": prebuilt.get("time", "")[:10],
                            "excerpt": f"Cached from World Monitor sweep at {prebuilt.get('time', 'unknown')}",
                            "source_id": f"wm_cache_{sig}",
                        })
                if signal_hits:
                    logger.info(
                        "[investigate_and_update] World Monitor cache: %d signal(s) injected for %s",
                        len(signal_hits), country,
                    )
                    for hit in signal_hits:
                        sig = str(hit.get("signal", "")).strip().upper()
                        if sig and sig not in new_observations:
                            new_observations.append(sig)
        except ImportError:
            pass  # World Monitor not available
        except Exception as _wm_err:
            logger.debug("[investigate_and_update] World Monitor fallback skipped: %s", _wm_err)

    # ── Rebuild StateContext focused on targeted signals ───────────────
    rebuild_query = query
    if targeted_signals:
        # Append signal tokens (structured) not free-text
        rebuild_query = f"{query} {' '.join(targeted_signals[:3])}".strip()

    new_ctx = build_initial_state(rebuild_query, country_code=country)

    # 5. Feed extracted signal evidence back into StateContext authority.
    if signal_hits:
        provenance_map = dict(getattr(new_ctx.evidence, "signal_provenance", {}) or {})
        for hit in list(signal_hits):
            signal = str(hit.get("signal", "") or "").strip().upper()
            if not signal:
                continue
            score = _clip01(hit.get("score", 0.6))
            source_name = str(hit.get("source") or "OSINT")
            url = str(hit.get("url") or "")
            date = _normalize_date(hit.get("publication_date"), fallback="")
            excerpt = _excerpt(hit.get("excerpt", ""))
            source_id = str(hit.get("source_id") or f"investigation_{signal}_{date}")

            evidence_row = Evidence(
                source=source_name,
                url=url,
                date=date,
                excerpt=excerpt,
                reliability=score,
                source_id=source_id,
            )
            new_ctx.provenance.attach(signal, evidence_row)

            # NOTE: signal_confidence is NO LONGER updated directly here.
            # It is gated through the Belief Accumulator below.
            # Raw scores go into provenance only (metadata, not belief).

            row_payload = evidence_row.to_dict()
            sig_rows = list(new_ctx.signal_evidence.get(signal, []) or [])
            key = (
                str(row_payload.get("source_id", "")),
                str(row_payload.get("publication_date", "")),
                str(row_payload.get("url", "")),
                str(row_payload.get("excerpt", "")),
            )
            known = {
                (
                    str(item.get("source_id", "")),
                    str(item.get("publication_date", "")),
                    str(item.get("url", "")),
                    str(item.get("excerpt", "")),
                )
                for item in sig_rows
                if isinstance(item, dict)
            }
            if key not in known:
                sig_rows.append(row_payload)
            new_ctx.signal_evidence[signal] = sig_rows

            prov_rows = list(provenance_map.get(signal, []) or [])
            prov_keys = {
                (
                    str(item.get("source_id", "")),
                    str(item.get("publication_date", "")),
                    str(item.get("url", "")),
                    str(item.get("excerpt", "")),
                )
                for item in prov_rows
                if isinstance(item, dict)
            }
            if key not in prov_keys:
                prov_rows.append(row_payload)
            provenance_map[signal] = prov_rows

        new_ctx.evidence.signal_provenance = provenance_map
        new_ctx.meta.source_count = int(max(int(getattr(new_ctx.meta, "source_count", 0) or 0), len(signal_hits)))
        new_ctx.observation_quality.is_observed = bool(new_ctx.observed_signals)
        new_ctx.observation_quality.source_count = int(
            max(int(getattr(new_ctx.observation_quality, "source_count", 0) or 0), len(signal_hits))
        )
        available_sources = max(
            1,
            int(getattr(new_ctx.observation_quality, "source_count", 0) or 0),
            len(signal_hits),
        )
        new_ctx.observation_quality.sensor_coverage = max(
            float(getattr(new_ctx.observation_quality, "sensor_coverage", 0.0) or 0.0),
            min(1.0, len(signal_hits) / float(available_sources)),
        )

    # ── 6. Belief-gated signal update ──────────────────────────────────
    # Raw evidence is attached above (provenance / signal_evidence).
    # But signal_confidence and observed_signals are ONLY updated when
    # the Belief Accumulator promotes observations → beliefs.
    # This prevents single low-reliability sources from altering state,
    # and collapses echo reporting (identical text across sites).
    _belief_gated = False
    if signal_hits:
        try:
            from engine.Layer3_StateModel.belief_accumulator import BeliefAccumulator, apply_beliefs_to_state

            all_observations: List[Dict[str, Any]] = []
            _seen_origins: set = set()

            for hit in signal_hits:
                obs = _observation_from_signal_hit(hit)
                if not obs:
                    continue
                origin_id = str(obs.get("origin_id", "") or "")
                if origin_id and origin_id in _seen_origins:
                    continue
                if origin_id:
                    _seen_origins.add(origin_id)
                all_observations.append(obs)
                continue

                excerpt = str(hit.get("excerpt", ""))[:600]
                url = str(hit.get("url", ""))
                source = str(hit.get("source", "")).lower()

                # Map MoltBot source names → assimilator source types
                if any(k in source for k in ("gov", "official", "state.gov", "mod.")):
                    src_type = "GOV"
                elif any(k in source for k in ("reuters", "ap", "bbc", "afp", "nyt")):
                    src_type = "NEWS"
                elif any(k in source for k in ("sipri", "gdelt", "worldbank", "ucdp")):
                    src_type = "DATASET"
                else:
                    src_type = "OSINT"  # default for web scrape

                # Dedup identical excerpts (same doc → multiple signal_hits)
                ekey = excerpt[:200]
                if ekey in _seen_excerpts:
                    continue
                _seen_excerpts.add(ekey)

                obs = extract_observations(excerpt, source_type=src_type, url=url)
                all_observations.extend(obs)

            # ── GDELT live event perception (investigation pass) ─────
            # Run the GDELT sensor alongside MoltBot observations.
            # GDELT events corroborate MoltBot articles (and vice versa)
            # through the shared BeliefAccumulator evaluation.
            try:
                from engine.Layer1_Collection.sensors.gdelt_sensor import sense_gdelt
                gdelt_obs = sense_gdelt(
                    countries=[str(country or "UNKNOWN").upper()],
                    hours_back=24,
                )
                if gdelt_obs:
                    all_observations.extend(gdelt_obs)
                    logger.info(
                        "[investigate_and_update] GDELT sensor: %d event observations injected",
                        len(gdelt_obs),
                    )
            except ImportError:
                pass  # GDELT adapter not installed
            except Exception as _gde:
                logger.debug("GDELT sensor skipped in investigation: %s", _gde)

            if all_observations:
                acc = BeliefAccumulator()
                beliefs = acc.evaluate(all_observations)
                updated_signals = apply_beliefs_to_state(new_ctx, beliefs)

                for belief in []:
                    sig = belief["signal"]
                    conf = _clip01(belief["confidence"])
                    existing = _clip01(new_ctx.signal_confidence.get(sig, 0.0))
                    new_ctx.signal_confidence[sig] = max(existing, conf)
                    if conf >= 0.35:
                        new_ctx.observed_signals.add(sig)

                _belief_gated = True
                logger.info(
                    "[investigate_and_update] Signals updated after belief application: %d",
                    len(updated_signals),
                )
                logger.info(
                    "[investigate_and_update] Belief accumulator: %d obs → %d beliefs promoted",
                    len(all_observations), len(beliefs),
                )
            else:
                logger.info("[investigate_and_update] No observations extracted from signal_hits")

        except ImportError as _ie:
            logger.warning("[investigate_and_update] Belief accumulator unavailable: %s", _ie)
        except Exception as _be:
            logger.warning("[investigate_and_update] Belief evaluation error: %s", _be)

    # Fallback: if belief accumulator unavailable, use direct scores (legacy)
    if signal_hits and not _belief_gated:
        logger.info("[investigate_and_update] Falling back to direct score update (no accumulator)")
        for hit in list(signal_hits):
            sig = str(hit.get("signal", "") or "").strip().upper()
            if not sig:
                continue
            score = _clip01(hit.get("score", 0.6))
            existing = _clip01(new_ctx.signal_confidence.get(sig, 0.0))
            merged = max(existing, score)
            new_ctx.signal_confidence[sig] = merged
            if merged >= 0.5:
                new_ctx.observed_signals.add(sig)

    from Config.config import ENABLE_LEGAL_MODULE as _LEGAL_ON
    if _LEGAL_ON:
        legal_flags = _apply_legal_reasoning(
            new_ctx,
            assessment_date=_normalize_date(current_state.get("date"), fallback=""),
        )
        print("LEGAL FLAGS:", legal_flags)
    else:
        legal_flags = []
        print("LEGAL FLAGS: [] (module disabled)")

    # ── RAG: DEFERRED TO POST-GATE (Pipeline Firewall) ─────────────
    # Legal evidence is no longer injected during investigation.
    # The coordinator handles RAG retrieval after the gate decision.
    logger.debug("[investigate_and_update] RAG deferred to post-gate (pipeline firewall)")

    economic_flags = _apply_economic_reasoning(
        new_ctx,
        assessment_date=_normalize_date(current_state.get("date"), fallback=""),
    )
    print("ECONOMIC FLAGS:", economic_flags)

    return new_ctx, new_observations

__all__ = [
    "build_initial_state",
    "investigate_and_update",
]
