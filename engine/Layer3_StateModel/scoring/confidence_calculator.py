"""
Confidence Calculator â€” The Master Gate
==========================================
This is the LAST module before Layer 4 receives any analysis.

Every conclusion, every dimension score, every assessment MUST carry
a confidence value computed by THIS module.

Layer 4 NEVER computes confidence. It only receives and explains it.

The master formula:

    confidence = (reliability Ã— freshness Ã— corroboration) âˆ’ contradiction_penalty

Where:
    reliability     = source trust from source_registry (0.0â€”1.0)
    freshness       = recency weight from freshness_model (0.0â€”1.0)
    corroboration   = multi-source support from corroboration_engine (0.0â€”1.0)
    contradiction   = penalty from contradiction_engine (0.0â€”0.5)

    The penalty is capped at 0.5 because contradictions reduce confidence
    but don't drive it to zero (the evidence still exists).

Output confidence levels:
    HIGH (â‰¥0.75):    Multiple fresh, reliable, corroborated sources. No contradictions.
    MODERATE (â‰¥0.50): Some gaps but core evidence is solid.
    LOW (â‰¥0.25):     Significant issues â€” use with caveats.
    INSUFFICIENT (<0.25): Do not use for decisions. Flag for collection.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import sys
import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from contracts.observation import ObservationRecord
from Core.orchestrator.knowledge_port import knowledge_port
from engine.Layer3_StateModel.validation.contradiction_engine import (
    contradiction_engine, Contradiction,
)
from engine.Layer3_StateModel.validation.freshness_model import (
    freshness_scorer, FreshnessScore,
)
from engine.Layer3_StateModel.validation.corroboration_engine import (
    corroboration_engine, CorroborationResult,
)
from engine.Layer3_StateModel.source_weighting import source_weighting

logger = logging.getLogger("confidence_calculator")


# =====================================================================
# Confidence Levels
# =====================================================================

CONFIDENCE_LEVELS = {
    "HIGH":         0.75,
    "MODERATE":     0.50,
    "LOW":          0.25,
    "INSUFFICIENT": 0.0,
}


# =====================================================================
# Component Weights (How much each factor matters)
# =====================================================================
# These are tunable. Current values based on intelligence analysis best practices.

DEFAULT_WEIGHTS = {
    "reliability":    0.30,   # Source trust
    "freshness":      0.30,   # Recency
    "corroboration":  0.25,   # Multi-source support
    "volume":         0.15,   # Number of observations (more data = slightly better)
}

# Maximum contradiction penalty (capped to prevent total zeroing)
MAX_CONTRADICTION_PENALTY = 0.40


# =====================================================================
# Confidence Report
# =====================================================================

@dataclass
class ConfidenceReport:
    """
    Complete confidence assessment for a set of observations.

    This is what Layer 4 receives alongside analyses.
    """
    # Overall
    overall_score: float = 0.0
    level: str = "INSUFFICIENT"
    explanation: str = ""

    # Component scores
    reliability_score: float = 0.0
    freshness_score: float = 0.0
    corroboration_score: float = 0.0
    volume_score: float = 0.0
    contradiction_penalty: float = 0.0

    # Details
    observation_count: int = 0
    source_count: int = 0
    contradiction_count: int = 0
    freshness_details: List[Dict] = field(default_factory=list)
    corroboration_details: List[Dict] = field(default_factory=list)
    contradiction_details: List[Dict] = field(default_factory=list)

    # Advisory
    warnings: List[str] = field(default_factory=list)
    computed_at: str = ""

    def __post_init__(self):
        if not self.computed_at:
            self.computed_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 4),
            "level": self.level,
            "explanation": self.explanation,
            "components": {
                "reliability": round(self.reliability_score, 4),
                "freshness": round(self.freshness_score, 4),
                "corroboration": round(self.corroboration_score, 4),
                "volume": round(self.volume_score, 4),
                "contradiction_penalty": round(self.contradiction_penalty, 4),
            },
            "observation_count": self.observation_count,
            "source_count": self.source_count,
            "contradiction_count": self.contradiction_count,
            "warnings": self.warnings,
            "computed_at": self.computed_at,
        }


# =====================================================================
# Confidence Calculator
# =====================================================================

class ConfidenceCalculator:
    """
    Computes confidence for an evidence set.

    Usage:
        calc = ConfidenceCalculator()
        report = calc.compute(observations, reference_date="2026-02-15")

        print(f"Confidence: {report.level} ({report.overall_score:.2f})")
        for w in report.warnings:
            print(f"  WARNING: {w}")
    """

    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or DEFAULT_WEIGHTS

    def compute(
        self,
        observations: List[ObservationRecord],
        reference_date: str = None,
    ) -> ConfidenceReport:
        """
        Compute confidence for a set of observations.

        This runs all four sub-engines and produces a master score.

        Args:
            observations: Evidence to assess
            reference_date: "Today" for the analysis

        Returns:
            ConfidenceReport with score, level, components, and warnings
        """
        if reference_date is None:
            reference_date = datetime.now().strftime("%Y-%m-%d")

        report = ConfidenceReport(
            observation_count=len(observations),
            computed_at=datetime.now().isoformat(),
        )

        if not observations:
            report.level = "INSUFFICIENT"
            report.explanation = "No observations provided."
            report.warnings.append("EMPTY: No evidence to assess.")
            return report

        # â”€â”€ Component 1: Reliability â”€â”€
        reliability = self._compute_reliability(observations, reference_date)
        report.reliability_score = reliability

        # â”€â”€ Component 2: Freshness â”€â”€
        freshness, freshness_details = self._compute_freshness(observations, reference_date)
        report.freshness_score = freshness
        report.freshness_details = freshness_details

        # â”€â”€ Component 3: Corroboration â”€â”€
        corroboration, corr_details = self._compute_corroboration(observations)
        report.corroboration_score = corroboration
        report.corroboration_details = corr_details

        # â”€â”€ Component 4: Volume â”€â”€
        volume = self._compute_volume(observations)
        report.volume_score = volume

        # â”€â”€ Contradiction Penalty â”€â”€
        penalty, contradiction_details = self._compute_contradiction_penalty(observations)
        report.contradiction_penalty = penalty
        report.contradiction_count = len(contradiction_details)
        report.contradiction_details = contradiction_details

        # â”€â”€ Source count â”€â”€
        report.source_count = len(set(obs.source for obs in observations))

        # â”€â”€ Master Formula â”€â”€
        raw_score = (
            self.weights["reliability"] * reliability +
            self.weights["freshness"] * freshness +
            self.weights["corroboration"] * corroboration +
            self.weights["volume"] * volume
        )

        # Apply contradiction penalty
        final_score = max(0.0, raw_score - penalty)
        report.overall_score = round(final_score, 4)

        # â”€â”€ Classify Level â”€â”€
        if final_score >= CONFIDENCE_LEVELS["HIGH"]:
            report.level = "HIGH"
        elif final_score >= CONFIDENCE_LEVELS["MODERATE"]:
            report.level = "MODERATE"
        elif final_score >= CONFIDENCE_LEVELS["LOW"]:
            report.level = "LOW"
        else:
            report.level = "INSUFFICIENT"

        # â”€â”€ Generate Explanation â”€â”€
        report.explanation = self._generate_explanation(report)

        # â”€â”€ Warnings â”€â”€
        report.warnings = self._generate_warnings(report, observations, reference_date)

        logger.info(
            f"Confidence: {report.level} ({report.overall_score:.2f}) "
            f"from {report.observation_count} observations, "
            f"{report.source_count} sources, "
            f"{report.contradiction_count} contradictions"
        )

        return report

    # â”€â”€ Component Calculators â”€â”€

    def _compute_reliability(
        self,
        observations: List[ObservationRecord],
        reference_date: str,
    ) -> float:
        """Average source trust across all observations with recency/corroboration weighting."""
        if not observations:
            return 0.0

        weighted_score = source_weighting.aggregate_score(observations, reference_date)
        if weighted_score > 0:
            return weighted_score

        trust_scores = []
        for obs in observations:
            trust = knowledge_port.get_source_trust(obs.source)
            trust_scores.append(trust * obs.confidence)
        return sum(trust_scores) / len(trust_scores) if trust_scores else 0.0

    def _compute_freshness(
        self,
        observations: List[ObservationRecord],
        reference_date: str,
    ) -> tuple:
        """Average freshness across all observations."""
        scores = freshness_scorer.score_batch(observations, reference_date)
        details = [s.to_dict() for s in scores]

        if not scores:
            return 0.0, details

        avg = sum(s.clamped_score for s in scores) / len(scores)
        return round(avg, 4), details

    def _compute_corroboration(
        self, observations: List[ObservationRecord]
    ) -> tuple:
        """Average corroboration across claim groups."""
        results = corroboration_engine.assess(observations)
        details = [r.to_dict() for r in results]

        if not results:
            return 0.0, details

        avg = sum(r.score for r in results) / len(results)
        return round(avg, 4), details

    def _compute_volume(self, observations: List[ObservationRecord]) -> float:
        """
        Volume score: more observations = more confidence (with diminishing returns).

        1 observation â†’ 0.2
        3 observations â†’ 0.5
        5+ observations â†’ 0.7
        10+ observations â†’ 0.9
        20+ observations â†’ 1.0
        """
        n = len(observations)
        if n == 0:
            return 0.0
        elif n <= 1:
            return 0.2
        elif n <= 3:
            return 0.3 + (n / 10.0)
        elif n <= 5:
            return 0.5 + (n / 25.0)
        elif n <= 10:
            return 0.7 + (n / 50.0)
        elif n <= 20:
            return 0.9
        else:
            return 1.0

    def _compute_contradiction_penalty(
        self, observations: List[ObservationRecord]
    ) -> tuple:
        """
        Contradiction penalty: sum of contradiction severities, capped.

        Each contradiction contributes its severity Ã— 0.1 to the penalty.
        Total penalty is capped at MAX_CONTRADICTION_PENALTY.
        """
        contradictions = contradiction_engine.detect(observations)
        details = [c.to_dict() for c in contradictions]

        if not contradictions:
            return 0.0, details

        raw_penalty = sum(c.severity * 0.1 for c in contradictions)
        capped = min(raw_penalty, MAX_CONTRADICTION_PENALTY)
        return round(capped, 4), details

    # â”€â”€ Report Generation â”€â”€

    def _generate_explanation(self, report: ConfidenceReport) -> str:
        """Generate a human-readable confidence explanation."""
        parts = []

        if report.level == "HIGH":
            parts.append("Strong evidence base.")
        elif report.level == "MODERATE":
            parts.append("Adequate evidence with some gaps.")
        elif report.level == "LOW":
            parts.append("Weak evidence â€” use with caution.")
        else:
            parts.append("Insufficient evidence for reliable analysis.")

        parts.append(
            f"{report.observation_count} observations from "
            f"{report.source_count} source(s)."
        )

        if report.contradiction_count > 0:
            parts.append(
                f"{report.contradiction_count} contradiction(s) detected "
                f"(penalty: -{report.contradiction_penalty:.2f})."
            )

        return " ".join(parts)

    def _generate_warnings(
        self,
        report: ConfidenceReport,
        observations: List[ObservationRecord],
        reference_date: str,
    ) -> List[str]:
        """Generate advisory warnings based on the assessment."""
        warnings = []

        # Single source
        if report.source_count == 1:
            src = observations[0].source if observations else "unknown"
            warnings.append(
                f"SINGLE_SOURCE: All evidence comes from '{src}'. "
                f"Requires cross-verification."
            )

        # Low freshness
        if report.freshness_score < 0.3:
            warnings.append(
                f"STALE_DATA: Average freshness is {report.freshness_score:.2f}. "
                f"Evidence may be outdated."
            )

        # Contradictions
        if report.contradiction_count >= 3:
            warnings.append(
                f"HIGH_CONTRADICTION: {report.contradiction_count} contradictions. "
                f"Evidence base is internally inconsistent."
            )

        # Low volume
        if report.observation_count <= 2:
            warnings.append(
                f"LOW_VOLUME: Only {report.observation_count} observation(s). "
                f"Assessment may be incomplete."
            )

        # Low corroboration
        if report.corroboration_score < 0.3:
            warnings.append(
                f"LOW_CORROBORATION: Score {report.corroboration_score:.2f}. "
                f"Most claims lack independent verification."
            )

        return warnings


# =====================================================================
# Module-Level Singleton
# =====================================================================

confidence_calculator = ConfidenceCalculator()


def update_confidence(
    old_confidence: float,
    new_information: float,
    existing_information: float,
) -> float:
    """
    Lightweight post-investigation confidence updater.
    """
    try:
        old = float(old_confidence)
    except Exception:
        old = 0.0
    try:
        new_info = max(0.0, float(new_information))
    except Exception:
        new_info = 0.0
    try:
        existing = max(0.0, float(existing_information))
    except Exception:
        existing = 0.0

    gain = new_info / (existing + 1.0)
    return min(1.0, max(0.0, old + 0.25 * gain))

__all__ = [
    "ConfidenceCalculator", "confidence_calculator",
    "ConfidenceReport",
    "update_confidence",
    "CONFIDENCE_LEVELS", "DEFAULT_WEIGHTS",
]
