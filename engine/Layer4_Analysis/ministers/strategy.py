"""StrategyMinister — cross-domain CAPABILITY classifier."""
from __future__ import annotations
from typing import Any, Dict, Optional

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.council_session import MinisterReport
from engine.Layer4_Analysis.ministers.base import BaseMinister
from engine.Layer6_Learning.reflection_log import format_reflections_for_prompt


class StrategyMinister(BaseMinister):
    def __init__(self):
        super().__init__("Strategy Minister")

    def _dimension(self) -> str:
        return "CAPABILITY"

    def deliberate(self, ctx: StateContext | Dict[str, Any]) -> Optional[MinisterReport]:
        ctx = self._coerce_state_context(ctx)
        if ctx is None:
            return None
            
        # Inject persistent reflection memory
        country_code = getattr(getattr(ctx, 'actors', None), 'subject_country', "UNKNOWN")
        reflections_prompt = format_reflections_for_prompt(country_code)
            
        instructions = "Classify cross-domain risk indicators without narrative or interpretation."
        if reflections_prompt:
            instructions += "\n" + reflections_prompt
            
        return self._ask_llm(
            state_context=ctx,
            specific_instructions=instructions,
        )
