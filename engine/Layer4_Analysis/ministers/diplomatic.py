"""DiplomaticMinister — INTENT dimension classifier."""
from __future__ import annotations
from typing import Any, Dict, Optional

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.council_session import MinisterReport
from engine.Layer4_Analysis.ministers.base import BaseMinister


class DiplomaticMinister(BaseMinister):
    def __init__(self):
        super().__init__("Diplomatic Minister")

    def _dimension(self) -> str:
        return "INTENT"

    def _pressure_classify(self, ctx: StateContext) -> Optional[MinisterReport]:
        """Pressure-based fallback for INTENT dimension."""
        raw_pressures = getattr(ctx, "pressures", {}) or {}
        if not raw_pressures:
            return None
        pressures = self._resolve_pressures(ctx)
        return self._pressure_report(
            pressure_value=pressures.get("intent_pressure", 0.0),
            high_signals=[
                "SIG_DIP_HOSTILITY",
                "SIG_ALLIANCE_ACTIVATION",
                "SIG_ALLIANCE_SHIFT",
                "SIG_NEGOTIATION_BREAKDOWN",
                "SIG_COERCIVE_PRESSURE",
                "SIG_COERCIVE_BARGAINING",
                "SIG_RETALIATORY_THREAT",
                "SIG_DETERRENCE_SIGNALING",
            ],
            medium_signals=[
                "SIG_DIP_HOSTILITY",
                "SIG_ALLIANCE_ACTIVATION",
                "SIG_ALLIANCE_SHIFT",
                "SIG_NEGOTIATION_BREAKDOWN",
                "SIG_COERCIVE_PRESSURE",
            ],
            low_signals=[
                "SIG_DIP_HOSTILITY",
                "SIG_ALLIANCE_ACTIVATION",
                "SIG_COERCIVE_PRESSURE",
            ],
            state_context=ctx,
        )

    def deliberate(self, ctx: StateContext | Dict[str, Any]) -> Optional[MinisterReport]:
        ctx = self._coerce_state_context(ctx)
        if ctx is None:
            return None
        return self._ask_llm(
            state_context=ctx,
            specific_instructions=(
                "Classify diplomatic-hostility, alliance-shift, negotiation-breakdown, "
                "coercive-bargaining, and deterrence-signaling indicators from numeric telemetry."
            ),
        )
