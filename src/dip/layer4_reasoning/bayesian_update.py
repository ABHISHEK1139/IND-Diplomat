"""
Bayesian Confidence Update
==========================
Uses pgmpy to mathematically update confidence (Prior -> Evidence -> Posterior)
without relying on LLM hallucination for percentages.
"""

import logging
from typing import Dict, List

try:
    from pgmpy.models import BayesianNetwork
    from pgmpy.factors.discrete import TabularCPD
    from pgmpy.inference import VariableElimination
except ImportError:
    BayesianNetwork = None
    TabularCPD = None
    VariableElimination = None

logger = logging.getLogger("Layer4.BayesianUpdate")


class BayesianConfidenceEngine:
    """
    Calculates posterior probability of a hypothesis given evidence verdicts 
    (YES/NO/PARTIAL) from the Evidence Judge and historical analogs.
    """
    def __init__(self):
        pass

    def calculate_posterior(self, prior: float, evidence_verdicts: List[str]) -> float:
        """
        Updates the prior probability based on evidence.
        Uses a simplified Bayesian Network model for demonstration.
        """
        if not BayesianNetwork:
            logger.warning("pgmpy not installed. Using simple heuristic update.")
            return self._heuristic_update(prior, evidence_verdicts)

        try:
            # Create a simple DAG: Hypothesis -> Evidence
            model = BayesianNetwork([('Hypothesis', 'Evidence')])
            
            # P(Hypothesis)
            cpd_h = TabularCPD(variable='Hypothesis', variable_card=2, values=[[1 - prior], [prior]])
            
            # P(Evidence | Hypothesis)
            # If Hypothesis is True (1), Evidence is more likely to be present (1)
            # 0: Evidence Absent, 1: Evidence Present
            cpd_e = TabularCPD(
                variable='Evidence', variable_card=2, 
                values=[
                    [0.8, 0.2], # P(E=0|H=0), P(E=0|H=1)
                    [0.2, 0.8]  # P(E=1|H=0), P(E=1|H=1)
                ],
                evidence=['Hypothesis'], evidence_card=[2]
            )
            
            model.add_cpds(cpd_h, cpd_e)
            
            # Aggregate evidence
            evidence_score = 0.5
            if evidence_verdicts:
                yes_count = evidence_verdicts.count("YES")
                no_count = evidence_verdicts.count("NO")
                if yes_count > no_count:
                    evidence_score = 1
                elif no_count > yes_count:
                    evidence_score = 0
                    
            if evidence_score == 0.5:
                return prior # Neutral evidence doesn't shift prior much
                
            inference = VariableElimination(model)
            posterior = inference.query(variables=['Hypothesis'], evidence={'Evidence': evidence_score})
            
            # Return P(Hypothesis = 1)
            return float(posterior.values[1])
            
        except Exception as e:
            logger.error(f"Bayesian update failed: {e}")
            return self._heuristic_update(prior, evidence_verdicts)

    def _heuristic_update(self, prior: float, evidence_verdicts: List[str]) -> float:
        """Fallback if pgmpy is not available."""
        current = prior
        for verdict in evidence_verdicts:
            if verdict == "YES":
                current = min(current + 0.1, 0.99)
            elif verdict == "NO":
                current = max(current - 0.1, 0.01)
        return current
