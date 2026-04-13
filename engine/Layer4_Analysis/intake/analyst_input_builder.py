"""
Build structured Layer-4 analyst input from Layer-3 state objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from engine.Layer3_StateModel.interface.state_provider import get_analysis_readiness
from engine.Layer4_Analysis.intake.question_scope_checker import check_question_scope
from engine.Layer4_Analysis.evidence.pressure_mapper import map_state_to_pressures


@dataclass
class AnalystInputBundle:
    question: str
    allowed: bool
    scope: str
    readiness: Dict[str, Any]
    country_states: Dict[str, Dict[str, Any]]
    relationship_state: Dict[str, Any]
    evidence_confidence: float
    strategic_pressures: Dict[str, float]
    briefing_text: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "allowed": self.allowed,
            "scope": self.scope,
            "readiness": self.readiness,
            "country_states": self.country_states,
            "relationship_state": self.relationship_state,
            "evidence_confidence": round(self.evidence_confidence, 4),
            "strategic_pressures": dict(self.strategic_pressures or {}),
            "briefing_text": self.briefing_text,
        }


def build_analyst_input(
    question: str,
    country_state: Any,
    relationship_state: Any,
    confidence: float | None = None,
    state_context: Any = None,
) -> Dict[str, Any]:
    """
    Convert state vectors into a structured intelligence brief.
    """
    scope = check_question_scope(question)
    readiness = get_analysis_readiness(
        country_state=country_state,
        relationship_state=relationship_state,
        confidence=confidence,
    )

    country_map = _normalize_country_states(country_state)
    relationship_map = _normalize_relationship_state(relationship_state)

    # Step 3: Allow Single-Actor Analysis (Auto-pair with ENVIRONMENT)
    if relationship_map.get("pair") == "unknown" and len(country_map) == 1:
        single_actor = list(country_map.keys())[0]
        relationship_map["pair"] = f"{single_actor}-ENVIRONMENT"
        relationship_map["main_drivers"] = ["structural_risk", "external_stability"]

    evidence_confidence = float(readiness.confidence)
    strategic_pressures: Dict[str, float] = {}
    if state_context is not None:
        try:
            pressure_obj = map_state_to_pressures(state_context)
            strategic_pressures = pressure_obj.to_dict()
            if hasattr(state_context, "pressures"):
                state_context.pressures = dict(strategic_pressures)
        except Exception:
            strategic_pressures = {}

    lines: List[str] = []
    lines.append("STRICT INSTRUCTION: You must base your analysis ONLY on the variables below. Do NOT use external knowledge or documents.")
    lines.append("COUNTRY STATES:")
    for country, summary in country_map.items():
        lines.append(f"{country}:")
        lines.append(f"- military signaling: {summary.get('military_signaling', 'unknown')}")
        lines.append(f"- diplomatic hostility: {summary.get('diplomatic_hostility', 'unknown')}")
        lines.append(f"- legal rhetoric: {summary.get('legal_rhetoric_trend', 'stable')}")
        lines.append(f"- economic pressure: {summary.get('economic_pressure', 'unknown')}")
        lines.append(f"- risk level: {summary.get('risk_level', 'unknown')}")

    lines.append("")
    lines.append("RELATIONSHIP:")
    lines.append(f"- pair: {relationship_map.get('pair', 'unknown')}")
    lines.append(f"- tension level: {relationship_map.get('tension_level', 'unknown')}")
    lines.append(f"- tension score: {relationship_map.get('tension_score', 0.0):.3f}")
    lines.append(f"- drivers: {', '.join(relationship_map.get('main_drivers', [])) or 'none'}")
    lines.append(f"- observations: {relationship_map.get('observation_count', 0)}")

    lines.append("")
    lines.append("EVIDENCE CONFIDENCE:")
    lines.append(
        f"- score: {evidence_confidence:.3f} ({_bucket_confidence(evidence_confidence)})"
    )
    lines.append(f"- readiness: {'ready' if readiness.ready else 'not_ready'}")
    if readiness.blockers:
        lines.append(f"- blockers: {'; '.join(readiness.blockers)}")

    lines.append("")
    lines.append("STRATEGIC PRESSURES:")
    if strategic_pressures:
        lines.append(f"- intent_pressure: {float(strategic_pressures.get('intent_pressure', 0.0)):.3f}")
        lines.append(f"- capability_pressure: {float(strategic_pressures.get('capability_pressure', 0.0)):.3f}")
        lines.append(f"- stability_pressure: {float(strategic_pressures.get('stability_pressure', 0.0)):.3f}")
        lines.append(f"- economic_pressure: {float(strategic_pressures.get('economic_pressure', 0.0)):.3f}")
    else:
        lines.append("- unavailable")

    lines.append("")
    lines.append("SCOPE:")
    lines.append(f"- allowed: {scope.allowed}")
    lines.append(f"- scope: {scope.scope}")
    lines.append(f"- note: {scope.reason}")

    bundle = AnalystInputBundle(
        question=question,
        allowed=bool(scope.allowed and readiness.ready),
        scope=scope.scope,
        readiness=readiness.to_dict(),
        country_states=country_map,
        relationship_state=relationship_map,
        evidence_confidence=evidence_confidence,
        strategic_pressures=strategic_pressures,
        briefing_text="\n".join(lines).strip(),
    )
    return bundle.to_dict()


def _normalize_country_states(country_state: Any) -> Dict[str, Dict[str, Any]]:
    if country_state is None:
        return {}

    if isinstance(country_state, dict) and "country_states" in country_state:
        states = country_state["country_states"]
        if isinstance(states, dict):
            return {key: _summarize_state(value) for key, value in states.items()}

    if isinstance(country_state, dict):
        code = str(country_state.get("country") or country_state.get("country_code") or "UNKNOWN")
        return {code: _summarize_state(country_state)}

    if isinstance(country_state, list):
        out: Dict[str, Dict[str, Any]] = {}
        for item in country_state:
            if not isinstance(item, dict):
                continue
            code = str(item.get("country") or item.get("country_code") or f"C{len(out)+1}")
            out[code] = _summarize_state(item)
        return out

    code = str(getattr(country_state, "country_code", "UNKNOWN"))
    as_dict = country_state.to_dict() if hasattr(country_state, "to_dict") else {}
    if not as_dict:
        as_dict = {
            "country": code,
            "risk_level": getattr(getattr(country_state, "overall_risk_level", None), "value", "unknown"),
            "legal_rhetoric_trend": getattr(country_state, "legal_rhetoric_trend", "stable"),
        }
    return {code: _summarize_state(as_dict)}


def _summarize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    dimensions = state.get("dimensions", {}) if isinstance(state, dict) else {}
    indices = state.get("indices", {}) if isinstance(state, dict) else {}
    legal_shift = (
        state.get("signal_breakdown", {}).get("legal_shift", {})
        if isinstance(state, dict) else {}
    )
    return {
        "military_signaling": _bucket(dimensions.get("military_pressure", {}).get("value")),
        "diplomatic_hostility": _bucket(dimensions.get("diplomatic_isolation", {}).get("value")),
        "economic_pressure": _bucket(dimensions.get("economic_stress", {}).get("value")),
        "tension_index": float(indices.get("tension_index", state.get("tension_index", 0.0) or 0.0)),
        "risk_level": str(state.get("risk_level") or state.get("overall_risk_level") or "unknown"),
        "legal_rhetoric_trend": str(
            state.get("legal_rhetoric_trend")
            or legal_shift.get("trend")
            or "stable"
        ),
        "recent_activity_signals": int(
            state.get("recent_activity_signals")
            or legal_shift.get("recent_signal_count")
            or 0
        ),
    }


def _normalize_relationship_state(relationship_state: Any) -> Dict[str, Any]:
    if relationship_state is None:
        return {
            "pair": "unknown",
            "tension_level": "unknown",
            "tension_score": 0.0,
            "main_drivers": [],
            "observation_count": 0,
        }

    if hasattr(relationship_state, "to_dict"):
        relationship_state = relationship_state.to_dict()

    if not isinstance(relationship_state, dict):
        return {
            "pair": "unknown",
            "tension_level": "unknown",
            "tension_score": 0.0,
            "main_drivers": [],
            "observation_count": 0,
        }

    countries = relationship_state.get("countries")
    pair = "unknown"
    if isinstance(countries, list) and len(countries) >= 2:
        pair = f"{countries[0]}-{countries[1]}"
    elif "country_a" in relationship_state and "country_b" in relationship_state:
        pair = f"{relationship_state.get('country_a')}-{relationship_state.get('country_b')}"

    evidence = relationship_state.get("supporting_evidence", [])
    if not isinstance(evidence, list):
        evidence = []

    return {
        "pair": pair,
        "tension_level": str(relationship_state.get("tension_level", "unknown")),
        "tension_score": float(relationship_state.get("tension_score", 0.0) or 0.0),
        "main_drivers": list(relationship_state.get("main_drivers", []) or []),
        "observation_count": int(
            relationship_state.get("observation_count")
            or relationship_state.get("confidence", {}).get("observation_count")
            or len(evidence)
        ),
    }


def _bucket(value: Any) -> str:
    try:
        score = float(value)
    except Exception:
        return "unknown"
    if score >= 0.70:
        return "high"
    if score >= 0.40:
        return "medium"
    return "low"


def _bucket_confidence(value: float) -> str:
    if value >= 0.70:
        return "high"
    if value >= 0.45:
        return "moderate"
    return "low"


__all__ = ["build_analyst_input", "AnalystInputBundle"]
