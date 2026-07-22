"""Domestic Minister — tests internal stability and regime pressure."""

from dip.layer4_reasoning.ministers.base import BaseMinister


class DomesticMinister(BaseMinister):
    """Hypothesis tester for internal instability and domestic pressure."""

    @property
    def minister_name(self) -> str:
        return "Domestic Minister"

    @property
    def hypothesis_type(self) -> str:
        return "Is domestic instability shaping the external behavior?"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a domestic-stability hypothesis tester. "
            "You do not advise policy. Your job is to predict observable "
            "signals that should appear if internal pressure, unrest, elite "
            "competition, legitimacy concerns, or diversionary incentives are "
            "driving the behavior.\n\n"
            "Think about: protests, elite splits, emergency powers, media "
            "control, domestic economic pain, leadership vulnerability, "
            "nationalist mobilization, and internal security deployments.\n\n"
            "Return ONLY the required JSON object."
        )
