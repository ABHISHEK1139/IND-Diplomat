import logging
from typing import List
from dip.core.schema import Signal, BayesianTrace, StateContext

logger = logging.getLogger("Layer3.BayesianTracker")

class BayesianTracker:
    """
    Formally calculates the posterior probability of a hypothesis
    given incoming Signals.
    """
    
    def __init__(self, initial_prior: float = 0.34):
        self.current_prior = initial_prior
        
    def update_beliefs(self, signals: List[Signal], hypothesis_label: str) -> List[BayesianTrace]:
        """
        Updates the probability iteratively for each signal.
        P(H|E) = [P(E|H) * P(H)] / P(E)
        We use a simplified odds-form update for demonstration.
        Odds(H|E) = LikelihoodRatio * Odds(H)
        """
        traces = []
        
        for sig in signals:
            # The likelihood ratio depends on the signal's confidence and intensity
            # E.g., if a military exercise is highly intense, it strongly supports Escalation.
            # Base Likelihood Ratio > 1 implies support. < 1 implies counter-evidence.
            
            # Simple heuristic: weight is based on confidence (0-1) and intensity (0-1)
            # High intensity + High confidence = high LR
            lr = 1.0 + (sig.intensity * sig.confidence)
            
            prior_odds = self.current_prior / (1.0 - self.current_prior + 1e-9)
            posterior_odds = prior_odds * lr
            posterior_prob = posterior_odds / (1.0 + posterior_odds)
            
            # Cap at 0.99 for extreme certainty avoidance
            posterior_prob = min(0.99, max(0.01, posterior_prob))
            
            trace = BayesianTrace(
                observation_id=sig.source_ref,
                prior_probability=round(self.current_prior, 3),
                posterior_probability=round(posterior_prob, 3),
                evidence_weight=round(lr, 3),
                hypothesis=hypothesis_label
            )
            
            traces.append(trace)
            self.current_prior = posterior_prob
            
        return traces
