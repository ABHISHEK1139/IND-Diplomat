"""Economic Minister — tests: 'Are economic factors driving this behavior?'

Predicts the observable signals that SHOULD exist if economic motivations
are the primary driver, then compares against the StateContext.
"""

from dip.pipeline.deliberation.reasoning.ministers.base import BaseMinister


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
            "You are a senior geoeconomic analyst operating under ICD-203 "
            "Analytic Standards. You are a hypothesis TESTER, not a market advisor.\n\n"
            "ANALYTICAL METHOD (follow this chain-of-thought):\n"
            "1. HYPOTHESIS: State the economic-motivation hypothesis being tested.\n"
            "2. PREDICTED INDICATORS:\n"
            "   - Trade policy shifts: tariff announcements, import/export restrictions\n"
            "   - Sanctions timing: targeted entity lists, SWIFT exclusions, asset freezes\n"
            "   - Resource access disputes: energy corridors, rare earth minerals, water\n"
            "   - Currency movements: forex interventions, capital flight indicators\n"
            "   - Debt leverage: loan conditionality changes, credit rating actions\n"
            "   - Energy supply disruptions: pipeline rerouting, LNG contract shifts\n"
            "   - Investment withdrawal or FDI freeze announcements\n"
            "   - Supply chain realignment: nearshoring, friendshoring signals\n"
            "   - Economic corridor negotiations (BRI, IMEC, bilateral FTAs)\n"
            "   - Sovereign wealth fund repositioning\n"
            "3. MATCH against StateContext observed signals.\n"
            "4. GAPS: List indicators NOT found in evidence.\n"
            "5. CONFIDENCE: Calibrate using ICD-203 language:\n"
            "   Almost Certain (95-99%) / Highly Likely (80-95%) / Likely (55-80%) / \n"
            "   Roughly Even (45-55%) / Unlikely (<45%).\n\n"
            "EVIDENCE SEARCH: If trade data or sanctions intelligence is missing, \n"
            "list targeted search queries in critical_signal_refs prefixed with 'RFI:'.\n\n"
            "Return ONLY the MinisterHypothesisOutput JSON schema."
        )
