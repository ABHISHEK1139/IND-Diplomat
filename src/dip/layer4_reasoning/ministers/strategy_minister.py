"""
Strategy Minister — tests: 'Is this escalation or de-escalation?'

Predicts the observable signals that SHOULD exist if the situation is
escalating (or de-escalating), then compares against the StateContext.
"""

from dip.layer4_reasoning.ministers.base import BaseMinister


class StrategyMinister(BaseMinister):
    """Hypothesis tester for escalation vs. de-escalation patterns."""

    @property
    def minister_name(self) -> str:
        return "Strategy Minister"

    @property
    def hypothesis_type(self) -> str:
        return "Is this escalation or de-escalation?"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a strategic-escalation hypothesis tester. "
            "You do NOT give opinions or assessments. Your ONLY job is: "
            "given a hypothesis about whether a situation is escalating or "
            "de-escalating, predict the specific, observable signals that "
            "SHOULD be present for each case.\n\n"
            "Think about: rhetoric intensity changes, diplomatic channel "
            "openings or closures, military posture shifts, alliance "
            "activation, sanctions announcements, ceasefire proposals, "
            "troop withdrawal or reinforcement, and backchannel activity.\n\n"
            "Return ONLY a JSON array of short signal description strings "
            "that would confirm escalation. If none match, the situation "
            "leans toward de-escalation."
        )
