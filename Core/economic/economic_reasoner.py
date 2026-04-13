"""
Deterministic economic reasoner.

Converts economic context telemetry into canonical economic escalation signals.
"""

from __future__ import annotations

from typing import Any, Dict, Set


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clip01(value: Any) -> float:
    return max(0.0, min(1.0, _as_float(value, 0.0)))


class EconomicReasoner:
    """
    Deterministic rule engine for economic-domain corroboration.
    """

    def supporting_metrics(self, state_context: Any) -> Dict[str, float]:
        economic = getattr(state_context, "economic", None)
        return {
            "sanctions": _clip01(getattr(economic, "sanctions", 0.0)),
            "economic_pressure": _clip01(getattr(economic, "economic_pressure", 0.0)),
            "trade_dependency": _clip01(getattr(economic, "trade_dependency", 0.0)),
        }

    def evaluate(self, state_context: Any, *, has_comtrade_evidence: bool = False) -> Set[str]:
        metrics = self.supporting_metrics(state_context)
        sanctions = metrics["sanctions"]
        economic_pressure = metrics["economic_pressure"]
        trade_dependency = metrics["trade_dependency"]

        flags: Set[str] = set()

        if sanctions >= 0.10:
            flags.add("SIG_ECO_SANCTIONS_ACTIVE")

        if economic_pressure >= 0.18:
            flags.add("SIG_ECO_PRESSURE_HIGH")

        if sanctions >= 0.10 and economic_pressure >= 0.12:
            flags.add("SIG_ECONOMIC_PRESSURE")

        if (
            trade_dependency >= 0.70
            and economic_pressure >= 0.20
            and bool(has_comtrade_evidence)
        ):
            flags.add("SIG_ECO_TRADE_LEVERAGE")

        return {str(flag or "").strip().upper() for flag in flags if str(flag or "").strip()}

