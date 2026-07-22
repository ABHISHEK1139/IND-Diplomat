"""
Security Minister — tests: 'Is this a genuine military threat?'

Predicts the observable signals that SHOULD exist if a genuine military
threat is present, then compares against the StateContext.
"""

from dip.layer4_reasoning.ministers.base import BaseMinister


class SecurityMinister(BaseMinister):
    """Hypothesis tester for genuine military threat assessment."""

    @property
    def minister_name(self) -> str:
        return "Security Minister"

    @property
    def hypothesis_type(self) -> str:
        return "Is this a genuine military threat?"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a military-intelligence hypothesis tester. "
            "You do NOT give opinions or assessments. Your ONLY job is: "
            "given a hypothesis about a genuine military threat, predict the "
            "specific, observable signals that SHOULD be present if the "
            "hypothesis is TRUE.\n\n"
            "Think about: troop movements, weapons deployments, mobilization "
            "orders, changes in military readiness levels, border "
            "reinforcements, air-defense activations, naval positioning, "
            "communications intercepts, and logistics surges.\n\n"
            "Return ONLY a JSON array of short signal description strings."
        )
