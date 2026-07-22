"""
Economic Minister — tests: 'Are economic factors driving this behavior?'

Predicts the observable signals that SHOULD exist if economic motivations
are the primary driver, then compares against the StateContext.
"""

from dip.layer4_reasoning.ministers.base import BaseMinister


class EconomicMinister(BaseMinister):
    """Hypothesis tester for economic drivers behind geopolitical behavior."""

    @property
    def minister_name(self) -> str:
        return "Economic Minister"

    @property
    def hypothesis_type(self) -> str:
        return "Are economic factors driving this behavior?"

    @property
    def system_prompt(self) -> str:
        return (
            "You are an economic-motivation hypothesis tester. "
            "You do NOT give opinions or assessments. Your ONLY job is: "
            "given a hypothesis about whether economic factors are the "
            "primary driver of observed geopolitical behavior, predict the "
            "specific, observable signals that SHOULD be present.\n\n"
            "Think about: trade policy changes, sanctions timing, resource "
            "access disputes, currency movements, debt leverage, energy "
            "supply disruptions, tariff announcements, investment "
            "withdrawal, supply-chain realignment, and economic-corridor "
            "negotiations.\n\n"
            "Return ONLY a JSON array of short signal description strings "
            "that would confirm economic motivation."
        )
