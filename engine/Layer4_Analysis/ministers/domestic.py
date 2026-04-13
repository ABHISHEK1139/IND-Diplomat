"""DomesticMinister — STABILITY dimension classifier."""
from __future__ import annotations
from typing import Any, Dict, Optional

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.council_session import MinisterReport
from engine.Layer4_Analysis.ministers.base import BaseMinister


class DomesticMinister(BaseMinister):
    def __init__(self):
        super().__init__("Domestic Minister")

    def _dimension(self) -> str:
        return "STABILITY"

    def _pressure_classify(self, ctx: StateContext) -> Optional[MinisterReport]:
        """Pressure-based fallback for STABILITY dimension."""
        raw_pressures = getattr(ctx, "pressures", {}) or {}
        if not raw_pressures:
            return None
        pressures = self._resolve_pressures(ctx)
        return self._pressure_report(
            pressure_value=pressures.get("stability_pressure", 0.0),
            high_signals=[
                "SIG_INTERNAL_INSTABILITY",
                "SIG_DECEPTION_ACTIVITY",
            ],
            medium_signals=["SIG_INTERNAL_INSTABILITY"],
            low_signals=["SIG_DECEPTION_ACTIVITY"],
            state_context=ctx,
        )

    def deliberate(self, ctx: StateContext | Dict[str, Any]) -> Optional[MinisterReport]:
        ctx = self._coerce_state_context(ctx)
        if ctx is None:
            return None
        return self._ask_llm(
            state_context=ctx,
            specific_instructions=(
                "Classify only deception and force-posture spillover indicators from numeric telemetry."
            ),
        )
