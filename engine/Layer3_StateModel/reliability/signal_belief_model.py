from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from engine.Layer3_StateModel.reliability.membership_functions import triangular, trapezoidal
from engine.Layer3_StateModel.reliability.signal_belief import SignalBelief


def _pick(root: Any, path: str, default: Any = None) -> Any:
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


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value or 0.0)))


def _mean(values: Iterable[float], default: float = 0.5) -> float:
    clean = [_clip01(v) for v in list(values or [])]
    if not clean:
        return _clip01(default)
    return _clip01(sum(clean) / len(clean))


class SignalBeliefModel:
    """
    Converts StateContext telemetry into graded signal beliefs.
    """

    def build_all(self, state: Any) -> List[SignalBelief]:
        merged: Dict[str, SignalBelief] = {}
        for row in self.interpret_military(state):
            self._merge(merged, row)
        for row in self.interpret_diplomatic_hostility(state):
            self._merge(merged, row)
        for row in self.interpret_sanctions(state):
            self._merge(merged, row)
        for row in self.interpret_domestic_unrest(state):
            self._merge(merged, row)
        for row in self.interpret_alliance_activation(state):
            self._merge(merged, row)
        for row in self.interpret_capabilities(state):
            self._merge(merged, row)
        return list(merged.values())

    @staticmethod
    def _merge(store: Dict[str, SignalBelief], row: SignalBelief) -> None:
        token = str(row.signal or "").strip().upper()
        if not token:
            return
        existing = store.get(token)
        if existing is None or row.belief > existing.belief:
            store[token] = row

    def _source_agreement(self, state: Any) -> float:
        direct = _pick(state, "meta.source_consistency", None)
        if direct is not None:
            return _clip01(_as_float(direct, 0.5))

        confidence = _as_float(_pick(state, "meta.data_confidence", 0.5), 0.5)
        source_count = _as_float(_pick(state, "meta.source_count", 0.0), 0.0)
        source_support = _clip01(source_count / 8.0)
        return _mean([confidence, source_support], default=0.5)

    def _temporal_stability(self, state: Any) -> float:
        direct = _pick(state, "temporal.stability", None)
        if direct is not None:
            return _clip01(_as_float(direct, 0.5))

        explicit = _pick(state, "meta.temporal_stability", None)
        if explicit is not None:
            return _clip01(_as_float(explicit, 0.5))

        recency = _clip01(_as_float(_pick(state, "meta.time_recency", 0.5), 0.5))
        volatility = _clip01(_as_float(_pick(state, "meta.event_volatility", 0.5), 0.5))
        return _mean([recency, 1.0 - volatility], default=0.5)

    def _belief_row(self, signal: str, belief: float, state: Any) -> SignalBelief:
        stable_belief = _clip01(belief)
        return SignalBelief(
            signal=signal,
            belief=stable_belief,
            uncertainty=1.0 - stable_belief,
            source_agreement=self._source_agreement(state),
            temporal_stability=self._temporal_stability(state),
        )

    def interpret_military(self, state: Any) -> List[SignalBelief]:
        mobilization = max(
            _as_float(_pick(state, "military.mobilization", 0.0), 0.0),
            _as_float(_pick(state, "military.mobilization_level", 0.0), 0.0),
        )

        mobilization_belief = triangular(mobilization, 0.45, 0.70, 0.90)
        posture_belief = triangular(mobilization, 0.40, 0.68, 0.95)

        return [
            self._belief_row("SIG_MIL_MOBILIZATION", mobilization_belief, state),
            self._belief_row("SIG_MIL_ESCALATION", mobilization_belief, state),
            self._belief_row("SIG_FORCE_POSTURE", posture_belief, state),
        ]

    def interpret_diplomatic_hostility(self, state: Any) -> List[SignalBelief]:
        hostility = max(
            _as_float(_pick(state, "diplomatic.hostility", 0.0), 0.0),
            _as_float(_pick(state, "diplomatic.hostility_tone", 0.0), 0.0),
        )
        hostility_belief = triangular(hostility, 0.40, 0.72, 0.96)
        return [
            self._belief_row("SIG_DIP_HOSTILITY", hostility_belief, state),
            self._belief_row("SIG_DIP_HOSTILE_RHETORIC", hostility_belief, state),
        ]

    def interpret_sanctions(self, state: Any) -> List[SignalBelief]:
        sanctions = max(
            _as_float(_pick(state, "economic.sanctions", 0.0), 0.0),
            _as_float(_pick(state, "economic.sanctions_pressure", 0.0), 0.0),
        )
        economic_pressure = max(
            sanctions,
            _as_float(_pick(state, "economic.economic_pressure", 0.0), 0.0),
        )

        sanctions_active = trapezoidal(sanctions, 0.15, 0.35, 0.85, 1.0)
        pressure_belief = triangular(economic_pressure, 0.20, 0.65, 0.95)

        return [
            self._belief_row("SIG_SANCTIONS_ACTIVE", sanctions_active, state),
            self._belief_row("SIG_ECO_SANCTIONS_ACTIVE", sanctions_active, state),
            self._belief_row("SIG_ECON_PRESSURE", pressure_belief, state),
            self._belief_row("SIG_ECONOMIC_PRESSURE", pressure_belief, state),
        ]

    def interpret_domestic_unrest(self, state: Any) -> List[SignalBelief]:
        unrest = max(
            _as_float(_pick(state, "domestic.unrest", 0.0), 0.0),
            _as_float(_pick(state, "domestic.protests", 0.0), 0.0),
            1.0 - _clip01(_as_float(_pick(state, "domestic.regime_stability", 0.5), 0.5)),
        )
        instability_belief = triangular(unrest, 0.25, 0.60, 0.95)
        return [
            self._belief_row("SIG_INTERNAL_INSTABILITY", instability_belief, state),
            self._belief_row("SIG_DOM_INTERNAL_INSTABILITY", instability_belief, state),
        ]

    def interpret_alliance_activation(self, state: Any) -> List[SignalBelief]:
        alliances = max(
            _as_float(_pick(state, "diplomatic.alliances", 0.0), 0.0),
            _as_float(_pick(state, "diplomatic.alliance_activity", 0.0), 0.0),
        )
        alliance_belief = triangular(alliances, 0.35, 0.70, 0.95)
        return [
            self._belief_row("SIG_ALLIANCE_ACTIVATION", alliance_belief, state),
            self._belief_row("SIG_ALLIANCE_SHIFT", alliance_belief, state),
        ]

    def interpret_capabilities(self, state: Any) -> List[SignalBelief]:
        logistics = max(
            _as_float(_pick(state, "capability.logistics_activity", 0.0), 0.0),
            _as_float(_pick(state, "capabilities.logistics_activity", 0.0), 0.0),
            _as_float(_pick(state, "capabilities.logistics", 0.0), 0.0),
        )
        cyber = max(
            _as_float(_pick(state, "capability.cyber_activity", 0.0), 0.0),
            _as_float(_pick(state, "capabilities.cyber_activity", 0.0), 0.0),
            _as_float(_pick(state, "capabilities.cyber", 0.0), 0.0),
        )
        negotiations = _clip01(_as_float(_pick(state, "diplomatic.negotiations", 0.5), 0.5))
        mobilization = max(
            _as_float(_pick(state, "military.mobilization", 0.0), 0.0),
            _as_float(_pick(state, "military.mobilization_level", 0.0), 0.0),
        )

        logistics_belief = triangular(logistics, 0.30, 0.65, 1.00)
        cyber_belief = triangular(cyber, 0.30, 0.65, 1.00)
        mobilization_belief = triangular(mobilization, 0.45, 0.70, 0.90)
        negotiation_breakdown = triangular(1.0 - negotiations, 0.25, 0.65, 1.00)
        deception_belief = _clip01((0.6 * mobilization_belief) + (0.4 * negotiation_breakdown))

        return [
            self._belief_row("SIG_LOGISTICS_PREP", logistics_belief, state),
            self._belief_row("SIG_LOGISTICS_SURGE", logistics_belief, state),
            self._belief_row("SIG_CYBER_ACTIVITY", cyber_belief, state),
            self._belief_row("SIG_CYBER_PREPARATION", cyber_belief, state),
            self._belief_row("SIG_DECEPTION_ACTIVITY", deception_belief, state),
            self._belief_row("SIG_NEGOTIATION_BREAKDOWN", negotiation_breakdown, state),
        ]

