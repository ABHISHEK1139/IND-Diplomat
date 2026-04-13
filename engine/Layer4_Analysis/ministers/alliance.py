"""AllianceMinister — alliance/diplomatic INTENT classifier."""
from __future__ import annotations
from typing import Any, Dict, Optional

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.council_session import MinisterReport
from engine.Layer4_Analysis.ministers.base import BaseMinister


class AllianceMinister(BaseMinister):
    def __init__(self):
        super().__init__("Alliance Minister")

    def _dimension(self) -> str:
        return "INTENT"

    def deliberate(self, ctx: StateContext | Dict[str, Any]) -> Optional[MinisterReport]:
        ctx = self._coerce_state_context(ctx)
        if ctx is None:
            return None
        return self._ask_llm(
            state_context=ctx,
            specific_instructions=(
                "Classify alliance-shift and diplomatic-hostility indicators from numeric telemetry."
            ),
        )
