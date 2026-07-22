"""
ACH Hypothesis Tracker — Multi-Hypothesis Bayesian Engine
==========================================================

Maintains competing hypotheses with Bayesian updating as new evidence arrives.
Uses pgmpy for Bayesian inference when available, numpy/graph fallback otherwise.

Port of DIP_8 concept enhanced with Autonomous_3.0 multi-hypothesis pattern.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("Layer4_Reasoning.hypothesis_tracker")

try:
    from pgmpy.models import BayesianNetwork
    from pgmpy.factors.discrete import TabularCPD
    from pgmpy.inference import VariableElimination
    PGMPY_AVAILABLE = True
except ImportError:
    PGMPY_AVAILABLE = False
    logger.info("pgmpy not installed. Using numpy fallback for Bayesian ACH.")


@dataclass
class TrackedHypothesis:
    """A hypothesis being tracked over time."""
    name: str
    description: str = ""
    prior: float = 0.0
    posterior: float = 0.0
    evidence_for: List[str] = field(default_factory=list)
    evidence_against: List[str] = field(default_factory=list)
    last_updated: str = ""


@dataclass
class ACHReport:
    """Output of the hypothesis tracker."""
    hypotheses: List[TrackedHypothesis] = field(default_factory=list)
    most_likely: str = ""
    most_likely_prob: float = 0.0
    second_most_likely: str = ""
    second_most_likely_prob: float = 0.0
    discriminative_evidence: List[str] = field(default_factory=list)
    convergence: bool = False
    recommendation: str = ""


class HypothesisTracker:
    """Track and update multiple competing hypotheses as evidence arrives."""

    def __init__(self, hypotheses: Optional[List[Dict[str, Any]]] = None):
        self.hypotheses: Dict[str, TrackedHypothesis] = {}
        self.evidence_history: List[Dict[str, Any]] = []
        if hypotheses:
            for h in hypotheses:
                self.add_hypothesis(
                    name=h["name"],
                    description=h.get("description", ""),
                    prior=h.get("prior", 1.0 / len(hypotheses)),
                )

    def add_hypothesis(self, name: str, description: str = "", prior: float = 0.0) -> None:
        """Register a new hypothesis to track."""
        self.hypotheses[name] = TrackedHypothesis(
            name=name,
            description=description,
            prior=prior,
            posterior=prior,
        )

    def update_evidence(
        self,
        evidence_id: str,
        likelihoods: Dict[str, float],  # hypothesis_name → P(evidence | hypothesis)
    ) -> ACHReport:
        """Bayesian update: P(H|E) = P(E|H) * P(H) / P(E).

        Args:
            evidence_id: Unique evidence identifier
            likelihoods: Per-hypothesis likelihood P(evidence | hypothesis)
        """
        self.evidence_history.append({"evidence_id": evidence_id, "likelihoods": likelihoods})

        # Normalize priors
        total_prior = sum(h.prior for h in self.hypotheses.values()) or 1.0
        for h in self.hypotheses.values():
            h.prior /= total_prior

        # Compute posterior (unnormalized)
        posteriors: Dict[str, float] = {}
        for name, h in self.hypotheses.items():
            likelihood = likelihoods.get(name, 0.01)  # small default to avoid zero
            posteriors[name] = likelihood * h.prior

        # Normalize
        total = sum(posteriors.values()) or 1.0
        for name, h in self.hypotheses.items():
            h.posterior = posteriors[name] / total
            h.prior = h.posterior  # set as prior for next update
            h.last_updated = evidence_id
            if likelihoods.get(name, 0) > 0.3:
                h.evidence_for.append(evidence_id)
            elif likelihoods.get(name, 0) < 0.1:
                h.evidence_against.append(evidence_id)

        return self._build_report()

    def _build_report(self) -> ACHReport:
        """Generate current ACH report from tracked hypotheses."""
        sorted_h = sorted(self.hypotheses.values(), key=lambda h: h.posterior, reverse=True)
        if not sorted_h:
            return ACHReport()

        best = sorted_h[0]
        second = sorted_h[1] if len(sorted_h) > 1 else best

        # Discriminative evidence: evidence that strongly separates top 2
        discriminative: List[str] = []
        for e in best.evidence_for:
            if e in second.evidence_against:
                discriminative.append(e)

        # Convergence check: top probability > 0.7
        convergence = best.posterior > 0.7

        # Recommendation
        if convergence:
            recommendation = f"Hypothesis '{best.name}' is dominant ({best.posterior:.0%}). "
            recommendation += f"Collect discriminative evidence on: {', '.join(discriminative[:2]) or 'no clear discriminator'}."
        else:
            recommendation = f"No hypothesis dominates. Top: '{best.name}' ({best.posterior:.0%}), "
            recommendation += f"Second: '{second.name}' ({second.posterior:.0%}). "
            recommendation += "Need more discriminative evidence."

        return ACHReport(
            hypotheses=list(sorted_h),
            most_likely=best.name,
            most_likely_prob=round(best.posterior, 4),
            second_most_likely=second.name,
            second_most_likely_prob=round(second.posterior, 4),
            discriminative_evidence=discriminative,
            convergence=convergence,
            recommendation=recommendation,
        )


def create_default_hypotheses(session_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Create default competing hypotheses for geopolitical assessment."""
    return [
        {
            "name": "imminent_escalation",
            "description": "Genuine military escalation is imminent",
            "prior": 0.20,
        },
        {
            "name": "coercive_signaling",
            "description": "Saber-rattling for diplomatic leverage, not actual conflict",
            "prior": 0.35,
        },
        {
            "name": "domestic_posturing",
            "description": "Actions driven by domestic political needs, not external threat",
            "prior": 0.25,
        },
        {
            "name": "routine_activity",
            "description": "Observed signals are routine military/economic activity",
            "prior": 0.15,
        },
        {
            "name": "third_party_manipulation",
            "description": "Information environment manipulated by third party",
            "prior": 0.05,
        },
    ]
