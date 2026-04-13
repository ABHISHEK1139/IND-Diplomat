"""
Knowledge-gap analyzer for hypothesis evidence coverage.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Set

from engine.Layer4_Analysis.evidence.evidence_requirements import canonical_hypothesis_name, requirements_for


class GapAnalyzer:
    """
    Compares required vs observed signals for a selected hypothesis.
    """

    HIGH_COVERAGE = 0.70
    LOW_COVERAGE = 0.40

    def analyze(self, hypothesis: str, observed_signals: Iterable[str]) -> Dict[str, Any]:
        canonical = canonical_hypothesis_name(hypothesis)
        required = set(requirements_for(canonical))
        observed = {str(item).strip() for item in set(observed_signals) if str(item).strip()}

        if not required:
            return {
                "hypothesis": canonical,
                "coverage": 1.0,
                "matched": [],
                "missing": [],
                "required": [],
                "observed": sorted(observed),
                "coverage_band": "unknown_hypothesis",
            }

        matched = required & observed
        missing = required - observed
        coverage = len(matched) / max(1, len(required))

        return {
            "hypothesis": canonical,
            "coverage": float(coverage),
            "matched": sorted(matched),
            "missing": sorted(missing),
            "required": sorted(required),
            "observed": sorted(observed),
            "coverage_band": self._coverage_band(coverage),
        }

    def _coverage_band(self, coverage: float) -> str:
        if coverage >= self.HIGH_COVERAGE:
            return "sufficient"
        if coverage >= self.LOW_COVERAGE:
            return "uncertain"
        return "insufficient"


__all__ = ["GapAnalyzer"]

