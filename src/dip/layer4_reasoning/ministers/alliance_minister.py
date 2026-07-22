"""Alliance Minister — tests alliance signaling and coalition movement."""

from dip.layer4_reasoning.ministers.base import BaseMinister


class AllianceMinister(BaseMinister):
    """Hypothesis tester for alliance activation and partner behavior."""

    @property
    def minister_name(self) -> str:
        return "Alliance Minister"

    @property
    def hypothesis_type(self) -> str:
        return "Are alliance dynamics changing the escalation path?"

    @property
    def system_prompt(self) -> str:
        return (
            "You are an alliance-dynamics hypothesis tester. "
            "You do not advise policy. Your job is to predict observable "
            "signals that should appear if allies, partners, coalitions, or "
            "security guarantees are changing the escalation path.\n\n"
            "Think about: joint statements, defense consultations, basing "
            "access, exercises, mutual defense language, arms transfers, "
            "coalition sanctions, mediation blocs, and partner restraint.\n\n"
            "Return ONLY the required JSON object."
        )
