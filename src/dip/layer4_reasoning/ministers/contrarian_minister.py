"""Contrarian Minister — tests the strongest alternative explanation."""

from dip.layer4_reasoning.ministers.base import BaseMinister


class ContrarianMinister(BaseMinister):
    """Hypothesis tester for deception, false positives, and de-escalation."""

    @property
    def minister_name(self) -> str:
        return "Contrarian Minister"

    @property
    def hypothesis_type(self) -> str:
        return "What is the strongest non-escalatory or deceptive explanation?"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a contrarian hypothesis tester. "
            "You do not reassure or alarm. Your job is to predict observable "
            "signals that would show the main escalation interpretation is "
            "wrong, exaggerated, deceptive, defensive, or missing an off-ramp.\n\n"
            "Think about: exercises mistaken for mobilization, defensive "
            "posturing, diplomatic backchannels, propaganda inflation, sensor "
            "bias, missing corroboration, economic constraints, and incentives "
            "for restraint.\n\n"
            "Return ONLY the required JSON object."
        )
