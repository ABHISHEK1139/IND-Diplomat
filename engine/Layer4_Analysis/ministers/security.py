"""SecurityMinister — CAPABILITY dimension classifier."""
from __future__ import annotations
from typing import Any, Dict, Optional

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.council_session import MinisterReport
from engine.Layer4_Analysis.ministers.base import BaseMinister


class SecurityMinister(BaseMinister):
    def __init__(self):
        super().__init__("Security Minister")

    def _dimension(self) -> str:
        return "CAPABILITY"

    def _pressure_classify(self, ctx: StateContext) -> Optional[MinisterReport]:
        """Pressure-based fallback for CAPABILITY dimension."""
        raw_pressures = getattr(ctx, "pressures", {}) or {}
        if not raw_pressures:
            return None
        pressures = self._resolve_pressures(ctx)
        return self._pressure_report(
            pressure_value=pressures.get("capability_pressure", 0.0),
            high_signals=[
                "SIG_MIL_ESCALATION",
                "SIG_FORCE_POSTURE",
                "SIG_LOGISTICS_PREP",
                "SIG_CYBER_ACTIVITY",
            ],
            medium_signals=[
                "SIG_FORCE_POSTURE",
                "SIG_LOGISTICS_PREP",
            ],
            low_signals=["SIG_FORCE_POSTURE"],
            state_context=ctx,
        )

    def deliberate(self, ctx: StateContext | Dict[str, Any]) -> Optional[MinisterReport]:
        ctx = self._coerce_state_context(ctx)
        if ctx is None:
            return None
        return self._ask_llm(
            state_context=ctx,
            specific_instructions=(
                "Classify only military, cyber, and force-posture indicators from numeric telemetry."
            ),
        )
