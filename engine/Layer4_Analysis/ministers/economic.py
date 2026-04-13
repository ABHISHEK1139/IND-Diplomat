"""EconomicMinister — COST dimension classifier."""
from __future__ import annotations
from typing import Any, Dict, Optional

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.council_session import MinisterReport
from engine.Layer4_Analysis.ministers.base import BaseMinister


class EconomicMinister(BaseMinister):
    def __init__(self):
        super().__init__("Economic Minister")

    def _dimension(self) -> str:
        return "COST"

    def _pressure_classify(self, ctx: StateContext) -> Optional[MinisterReport]:
        """Pressure-based fallback for COST dimension."""
        raw_pressures = getattr(ctx, "pressures", {}) or {}
        if not raw_pressures:
            return None
        pressures = self._resolve_pressures(ctx)
        return self._pressure_report(
            pressure_value=pressures.get("economic_pressure", 0.0),
            high_signals=[
                "SIG_ECON_PRESSURE",
                "SIG_ECONOMIC_PRESSURE",
                "SIG_SANCTIONS_ACTIVE",
            ],
            medium_signals=[
                "SIG_ECON_PRESSURE",
                "SIG_ECONOMIC_PRESSURE",
            ],
            low_signals=None,
            state_context=ctx,
        )

    def deliberate(self, ctx: StateContext | Dict[str, Any]) -> Optional[MinisterReport]:
        ctx = self._coerce_state_context(ctx)
        if ctx is None:
            return None
        return self._ask_llm(
            state_context=ctx,
            specific_instructions=(
                "Classify only economic pressure and alliance-shift indicators from numeric telemetry."
            ),
        )
