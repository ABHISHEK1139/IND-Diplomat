"""
Diplomacy Minister — tests: 'Is this diplomatic posturing or genuine negotiation?'

Predicts the observable signals that SHOULD exist if diplomatic activity
represents real negotiation (vs. posturing), then compares against the StateContext.
"""

from dip.layer4_reasoning.ministers.base import BaseMinister


class DiplomacyMinister(BaseMinister):
    """Hypothesis tester for diplomatic posturing vs. genuine negotiation."""

    @property
    def minister_name(self) -> str:
        return "Diplomacy Minister"

    @property
    def hypothesis_type(self) -> str:
        return "Is this diplomatic posturing or genuine negotiation?"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a diplomatic-behavior hypothesis tester. "
            "You do NOT give opinions or assessments. Your ONLY job is: "
            "given a hypothesis about whether diplomatic activity is genuine "
            "negotiation or mere posturing, predict the specific, observable "
            "signals that SHOULD be present if genuine negotiation is "
            "occurring.\n\n"
            "Think about: envoy dispatches, back-channel communications, "
            "concession offers, draft agreement leaks, mediator involvement, "
            "precondition adjustments, public vs. private messaging "
            "consistency, summit scheduling, and working-group formation.\n\n"
            "Return ONLY a JSON array of short signal description strings "
            "that would confirm genuine negotiation. If none match, the "
            "activity leans toward posturing."
        )
