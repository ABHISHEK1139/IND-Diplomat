"""
Layer-5 Intelligence Assessment Report (IAR) builder.

Produces a deterministic, auditable report structure from Layer-3/Layer-4 outputs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from engine.Layer4_Analysis.counterfactual_engine import rank_causal_signals
from engine.Layer4_Analysis.evidence.signal_ontology import canonicalize_signal_token
from engine.Layer4_Analysis.schema import Hypothesis


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _normalize_signal(token: Any) -> str:
    """Delegate to the authoritative signal ontology normaliser."""
    canon = canonicalize_signal_token(str(token or ""))
    return canon if canon else str(token or "").strip().upper()


def _normalize_list(items: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for item in list(items or []):
        token = _normalize_signal(item)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _as_mapping(value: Any) -> Dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _extract_decision(council_payload: Dict[str, Any]) -> str:
    session = _as_mapping(council_payload.get("council_session"))
    for key in ("king_decision", "final_decision", "threat_level", "strategic_status", "status"):
        token = str(session.get(key, "") or "").strip()
        if token:
            return token.upper()

    answer = str(council_payload.get("answer", "") or "").upper()
    for label in ("CRITICAL", "HIGH", "ELEVATED", "GUARDED", "LOW", "ANOMALY"):
        if label in answer:
            return label
    return "UNKNOWN"


def _verification_score(council_payload: Dict[str, Any]) -> float:
    session = _as_mapping(council_payload.get("council_session"))
    for key in ("verification_score", "logic_score"):
        if key in session:
            return max(0.0, min(1.0, _safe_float(session.get(key), 0.0)))
    return max(0.0, min(1.0, _safe_float(council_payload.get("confidence"), 0.0)))


def _extract_observed_signals(state_context: Any, council_payload: Dict[str, Any]) -> List[str]:
    state_signals = _normalize_list(getattr(state_context, "observed_signals", []) or [])
    if state_signals:
        return state_signals
    session = _as_mapping(council_payload.get("council_session"))
    reports = _as_mapping(session.get("minister_reports"))
    recovered: List[str] = []
    for row in reports.values():
        payload = _as_mapping(row)
        predicted = _normalize_list(payload.get("predicted_signals", []) or [])
        recovered.extend(predicted)
    return _normalize_list(recovered)


def _dimension_from_name(name: str) -> str:
    token = str(name or "").strip().lower()
    if "security" in token:
        return "CAPABILITY"
    if "diplomatic" in token:
        return "INTENT"
    if "domestic" in token:
        return "STABILITY"
    if "economic" in token:
        return "COST"
    return "UNKNOWN"


def _build_counterfactual_session(
    state_context: Any,
    council_payload: Dict[str, Any],
    observed_signals: Sequence[str],
) -> Optional[Any]:
    session_payload = _as_mapping(council_payload.get("council_session"))
    reports = _as_mapping(session_payload.get("minister_reports"))
    if not reports:
        return None

    observed = set(_normalize_list(observed_signals))
    hypotheses: List[Hypothesis] = []

    for minister_name, report in reports.items():
        payload = _as_mapping(report)
        predicted = _normalize_list(payload.get("predicted_signals", []) or [])
        matched = [token for token in predicted if token in observed]
        missing = [token for token in predicted if token not in observed]
        coverage = _safe_float(payload.get("coverage"), -1.0)
        if coverage < 0.0:
            coverage = len(matched) / max(len(predicted), 1)

        hypotheses.append(
            Hypothesis(
                minister=str(minister_name or "UNKNOWN"),
                predicted_signals=predicted,
                matched_signals=matched,
                missing_signals=missing,
                coverage=max(0.0, min(1.0, coverage)),
                dimension=str(payload.get("dimension") or _dimension_from_name(str(minister_name or ""))).upper(),
            )
        )

    if not hypotheses:
        return None

    decision = _extract_decision(council_payload)
    pseudo = SimpleNamespace(
        state_context=state_context,
        hypotheses=hypotheses,
        final_decision=decision,
        king_decision=decision,
        net_escalation=_safe_float(session_payload.get("net_escalation"), 0.0),
        evidence_log=list(observed),
    )
    return pseudo


def _counterfactual_bundle(
    state_context: Any,
    council_payload: Dict[str, Any],
    observed_signals: Sequence[str],
) -> Tuple[List[str], List[Dict[str, Any]]]:
    pseudo_session = _build_counterfactual_session(state_context, council_payload, observed_signals)
    if pseudo_session is None:
        return [], []

    try:
        rows = list(rank_causal_signals(pseudo_session, signals=list(observed_signals)) or [])
    except Exception:
        rows = []
    if not rows:
        return [], []

    drivers: List[str] = []
    for row in rows:
        payload = _as_mapping(row)
        if bool(payload.get("changed", False)):
            token = _normalize_signal(payload.get("signal"))
            if token:
                drivers.append(token)
    return _normalize_list(drivers), rows


def _evidence_rows_for_signal(state_context: Any, signal: str) -> List[Dict[str, Any]]:
    token = _normalize_signal(signal)
    if not token:
        return []

    evidence_map = _as_mapping(getattr(state_context, "signal_evidence", {}) or {})
    rows = list(evidence_map.get(token, []) or [])

    if not rows:
        provenance = getattr(state_context, "provenance", None)
        get_fn = getattr(provenance, "get", None)
        if callable(get_fn):
            try:
                rows = list(get_fn(token) or [])
            except Exception:
                rows = []

    if not rows:
        evidence_ctx = getattr(state_context, "evidence", None)
        prov_map = _as_mapping(getattr(evidence_ctx, "signal_provenance", {}) if evidence_ctx is not None else {})
        rows = list(prov_map.get(token, []) or [])

    normalized: List[Dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            payload = dict(row)
        else:
            payload = {
                "source": str(getattr(row, "source", getattr(row, "source_name", "unknown")) or "unknown"),
                "url": str(getattr(row, "url", "") or ""),
                "date": str(getattr(row, "date", getattr(row, "publication_date", "")) or ""),
                "excerpt": str(getattr(row, "excerpt", getattr(row, "content", "")) or ""),
                "reliability": _safe_float(getattr(row, "reliability", getattr(row, "confidence", 0.0)), 0.0),
            }

        normalized.append(
            {
                "signal": token,
                "source": str(payload.get("source") or payload.get("source_name") or "unknown"),
                "url": str(payload.get("url") or ""),
                "date": str(payload.get("date") or payload.get("publication_date") or ""),
                "excerpt": str(payload.get("excerpt") or payload.get("content") or ""),
                "reliability": max(0.0, min(1.0, _safe_float(payload.get("reliability", payload.get("confidence", 0.0)), 0.0))),
            }
        )
    return normalized


@dataclass
class IntelligenceReport:
    executive_summary: str
    situation_overview: str
    key_indicators: List[str]
    causal_analysis: str
    constraint_analysis: str
    counterfactuals: List[str]
    evidence_sources: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_executive_summary(
    decision: str,
    confidence: float,
    causal_drivers: Sequence[str],
) -> str:
    drivers = ", ".join(_normalize_list(causal_drivers)) if causal_drivers else "none identified"
    return (
        f"ASSESSMENT: {decision}\n\n"
        f"The system assesses the current geopolitical posture as {decision} "
        f"with confidence {max(0.0, min(1.0, confidence)):.2f}.\n\n"
        f"Primary drivers: {drivers}"
    )


def build_situation_overview(state_context: Any) -> str:
    military = getattr(state_context, "military", None)
    diplomatic = getattr(state_context, "diplomatic", None)
    domestic = getattr(state_context, "domestic", None)
    economic = getattr(state_context, "economic", None)

    mobilization = _safe_float(getattr(military, "mobilization_level", 0.0), 0.0)
    rhetoric = _safe_float(getattr(diplomatic, "hostility_tone", 0.0), 0.0)
    stance = str(getattr(diplomatic, "official_stance", "unknown") or "unknown")
    stability = _safe_float(getattr(domestic, "regime_stability", 0.0), 0.0)
    unrest = _safe_float(getattr(domestic, "unrest", 0.0), 0.0)
    econ_pressure = _safe_float(getattr(economic, "economic_pressure", 0.0), 0.0)

    return (
        f"Military posture: mobilization index {mobilization:.2f}\n"
        f"Diplomatic posture: hostility {rhetoric:.2f} ({stance})\n"
        f"Domestic stability: {stability:.2f} (unrest {unrest:.2f})\n"
        f"Economic pressure: {econ_pressure:.2f}"
    )


def build_key_indicators(observed_signals: Sequence[str]) -> List[str]:
    return _normalize_list(observed_signals)


def build_causal_analysis(
    decision: str,
    causal_drivers: Sequence[str],
    counterfactual_rows: Sequence[Dict[str, Any]],
) -> str:
    drivers = _normalize_list(causal_drivers)
    if not drivers:
        return (
            f"The current decision ({decision}) does not have uniquely discriminating causal indicators "
            "under counterfactual testing."
        )

    strongest = []
    for row in list(counterfactual_rows or []):
        payload = _as_mapping(row)
        if not bool(payload.get("changed", False)):
            continue
        sig = _normalize_signal(payload.get("signal"))
        alt = str(payload.get("counterfactual_decision", "") or "").upper()
        if sig and alt:
            strongest.append(f"{sig}->{alt}")
        if len(strongest) >= 3:
            break

    qualifier = f" Key shifts: {', '.join(strongest)}." if strongest else ""
    return (
        "Escalation is driven by the following causal indicators: "
        f"{', '.join(drivers)}. Removing these signals changes the council decision.{qualifier}"
    )


def build_constraint_analysis(state_context: Any) -> str:
    constraints = getattr(state_context, "constraints", None)
    if constraints is None:
        return "Strategic constraints unavailable in state context."

    economic_risk = _safe_float(getattr(constraints, "economic_risk", 0.0), 0.0)
    political_risk = _safe_float(getattr(constraints, "political_risk", 0.0), 0.0)
    international_pressure = _safe_float(getattr(constraints, "international_pressure", 0.0), 0.0)
    military_cost = _safe_float(getattr(constraints, "military_readiness_cost", 0.0), 0.0)
    total_fn = getattr(constraints, "total_constraint", None)
    total = _safe_float(total_fn() if callable(total_fn) else 0.0, 0.0)

    return (
        "Escalation is limited by:\n"
        f"Economic risk: {economic_risk:.2f}\n"
        f"Political risk: {political_risk:.2f}\n"
        f"International pressure: {international_pressure:.2f}\n"
        f"Military readiness cost: {military_cost:.2f}\n"
        f"Aggregate constraint: {total:.2f}"
    )


def build_counterfactuals(
    counterfactual_rows: Sequence[Dict[str, Any]],
    causal_drivers: Sequence[str],
) -> List[str]:
    drivers = set(_normalize_list(causal_drivers))
    findings: List[str] = []

    for row in list(counterfactual_rows or []):
        payload = _as_mapping(row)
        signal = _normalize_signal(payload.get("signal"))
        if not signal:
            continue
        changed = bool(payload.get("changed", False))
        original_decision = str(payload.get("original_decision", "") or "").upper()
        cf_decision = str(payload.get("counterfactual_decision", "") or "").upper()
        delta_net = _safe_float(payload.get("delta_net"), 0.0)

        if changed and (not drivers or signal in drivers):
            findings.append(
                f"Removing {signal} changes decision {original_decision} -> {cf_decision} "
                f"(delta_net={delta_net:.2f})."
            )
        elif len(findings) < 3:
            findings.append(
                f"Removing {signal} does not change decision (delta_net={delta_net:.2f})."
            )

    return findings[:10]


def build_evidence(state_context: Any, observed_signals: Sequence[str]) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, str, str]] = set()
    for signal in _normalize_list(observed_signals):
        for row in _evidence_rows_for_signal(state_context, signal):
            key = (
                str(row.get("signal", "")),
                str(row.get("source", "")),
                str(row.get("url", "")),
                str(row.get("date", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            refs.append(row)
    return refs


def generate_report(
    *,
    council_payload: Dict[str, Any],
    state_context: Any,
    query: str = "",
) -> IntelligenceReport:
    decision = _extract_decision(council_payload)
    confidence = _verification_score(council_payload)
    observed_signals = _extract_observed_signals(state_context, council_payload)

    causal_drivers, counterfactual_rows = _counterfactual_bundle(
        state_context=state_context,
        council_payload=council_payload,
        observed_signals=observed_signals,
    )
    evidence_sources = build_evidence(state_context, observed_signals)

    report = IntelligenceReport(
        executive_summary=build_executive_summary(
            decision=decision,
            confidence=confidence,
            causal_drivers=causal_drivers,
        ),
        situation_overview=build_situation_overview(state_context),
        key_indicators=build_key_indicators(observed_signals),
        causal_analysis=build_causal_analysis(
            decision=decision,
            causal_drivers=causal_drivers,
            counterfactual_rows=counterfactual_rows,
        ),
        constraint_analysis=build_constraint_analysis(state_context),
        counterfactuals=build_counterfactuals(
            counterfactual_rows=counterfactual_rows,
            causal_drivers=causal_drivers,
        ),
        evidence_sources=evidence_sources,
    )
    return report


__all__ = ["IntelligenceReport", "generate_report"]

