"""
Baseline Model — Country Behavior Normalization
==================================================
Why this matters:

    Israel has frequent military events NORMALLY.
    Switzerland does not.

    If both show 5 military events:
    Your system thinks they are equal escalation.

    They are NOT.

    Israel: 5 events = Tuesday.
    Switzerland: 5 events = national crisis.

This module defines "normal behavior" per country so the system detects:
    "ABNORMAL escalation" instead of "events happened."

Design:
    Pre-computed baselines from historical averages.
    Anomaly = (observed - baseline_mean) / baseline_stddev

    z-score ≥ 2.0 → significant anomaly
    z-score ≥ 3.0 → extreme anomaly

    These baselines are bootstrapped from domain expertise
    and should be updated with real historical data when available.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import math
import logging

logger = logging.getLogger("baseline_model")


# =====================================================================
# Country Behavior Baselines
# =====================================================================
# Format: {country_code: {dimension: {"mean": float, "stddev": float}}}
#
# These represent "normal monthly behavior" for each country.
# Sources: GDELT historical averages, SIPRI data, expert calibration.
#
# Dimensions match country_state_builder's 5 dimensions:
#   conflict_activity, military_pressure, economic_stress,
#   diplomatic_isolation, internal_stability

COUNTRY_BASELINES: Dict[str, Dict[str, Dict[str, float]]] = {
    # High-conflict baseline countries (elevated normal)
    "ISR": {
        "conflict_activity":    {"mean": 0.65, "stddev": 0.12},
        "military_pressure":    {"mean": 0.60, "stddev": 0.15},
        "economic_stress":      {"mean": 0.35, "stddev": 0.10},
        "diplomatic_isolation": {"mean": 0.55, "stddev": 0.12},
        "internal_stability":   {"mean": 0.45, "stddev": 0.10},
    },
    "RUS": {
        "conflict_activity":    {"mean": 0.55, "stddev": 0.15},
        "military_pressure":    {"mean": 0.65, "stddev": 0.12},
        "economic_stress":      {"mean": 0.50, "stddev": 0.12},
        "diplomatic_isolation": {"mean": 0.60, "stddev": 0.10},
        "internal_stability":   {"mean": 0.40, "stddev": 0.08},
    },
    "UKR": {
        "conflict_activity":    {"mean": 0.70, "stddev": 0.10},
        "military_pressure":    {"mean": 0.70, "stddev": 0.10},
        "economic_stress":      {"mean": 0.60, "stddev": 0.12},
        "diplomatic_isolation": {"mean": 0.30, "stddev": 0.10},
        "internal_stability":   {"mean": 0.50, "stddev": 0.12},
    },
    "PAK": {
        "conflict_activity":    {"mean": 0.50, "stddev": 0.15},
        "military_pressure":    {"mean": 0.50, "stddev": 0.12},
        "economic_stress":      {"mean": 0.55, "stddev": 0.12},
        "diplomatic_isolation": {"mean": 0.40, "stddev": 0.10},
        "internal_stability":   {"mean": 0.50, "stddev": 0.12},
    },

    # Medium-baseline countries
    "IND": {
        "conflict_activity":    {"mean": 0.40, "stddev": 0.12},
        "military_pressure":    {"mean": 0.45, "stddev": 0.10},
        "economic_stress":      {"mean": 0.35, "stddev": 0.10},
        "diplomatic_isolation": {"mean": 0.25, "stddev": 0.08},
        "internal_stability":   {"mean": 0.35, "stddev": 0.10},
    },
    "CHN": {
        "conflict_activity":    {"mean": 0.40, "stddev": 0.10},
        "military_pressure":    {"mean": 0.55, "stddev": 0.10},
        "economic_stress":      {"mean": 0.30, "stddev": 0.08},
        "diplomatic_isolation": {"mean": 0.45, "stddev": 0.10},
        "internal_stability":   {"mean": 0.30, "stddev": 0.08},
    },
    "USA": {
        "conflict_activity":    {"mean": 0.45, "stddev": 0.12},
        "military_pressure":    {"mean": 0.60, "stddev": 0.10},
        "economic_stress":      {"mean": 0.25, "stddev": 0.08},
        "diplomatic_isolation": {"mean": 0.20, "stddev": 0.05},
        "internal_stability":   {"mean": 0.30, "stddev": 0.10},
    },
    "IRN": {
        "conflict_activity":    {"mean": 0.50, "stddev": 0.15},
        "military_pressure":    {"mean": 0.55, "stddev": 0.12},
        "economic_stress":      {"mean": 0.60, "stddev": 0.10},
        "diplomatic_isolation": {"mean": 0.70, "stddev": 0.10},
        "internal_stability":   {"mean": 0.50, "stddev": 0.12},
    },
    "PRK": {
        "conflict_activity":    {"mean": 0.55, "stddev": 0.15},
        "military_pressure":    {"mean": 0.65, "stddev": 0.12},
        "economic_stress":      {"mean": 0.70, "stddev": 0.08},
        "diplomatic_isolation": {"mean": 0.85, "stddev": 0.05},
        "internal_stability":   {"mean": 0.35, "stddev": 0.08},
    },

    # Low-baseline countries (typically peaceful)
    "CHE": {
        "conflict_activity":    {"mean": 0.05, "stddev": 0.03},
        "military_pressure":    {"mean": 0.05, "stddev": 0.03},
        "economic_stress":      {"mean": 0.10, "stddev": 0.05},
        "diplomatic_isolation": {"mean": 0.10, "stddev": 0.05},
        "internal_stability":   {"mean": 0.10, "stddev": 0.05},
    },
    "JPN": {
        "conflict_activity":    {"mean": 0.15, "stddev": 0.08},
        "military_pressure":    {"mean": 0.20, "stddev": 0.08},
        "economic_stress":      {"mean": 0.25, "stddev": 0.08},
        "diplomatic_isolation": {"mean": 0.10, "stddev": 0.05},
        "internal_stability":   {"mean": 0.15, "stddev": 0.05},
    },
    "AUS": {
        "conflict_activity":    {"mean": 0.10, "stddev": 0.05},
        "military_pressure":    {"mean": 0.20, "stddev": 0.08},
        "economic_stress":      {"mean": 0.20, "stddev": 0.08},
        "diplomatic_isolation": {"mean": 0.10, "stddev": 0.05},
        "internal_stability":   {"mean": 0.10, "stddev": 0.05},
    },
    "DEU": {
        "conflict_activity":    {"mean": 0.10, "stddev": 0.05},
        "military_pressure":    {"mean": 0.15, "stddev": 0.05},
        "economic_stress":      {"mean": 0.25, "stddev": 0.08},
        "diplomatic_isolation": {"mean": 0.10, "stddev": 0.05},
        "internal_stability":   {"mean": 0.15, "stddev": 0.05},
    },
    "GBR": {
        "conflict_activity":    {"mean": 0.20, "stddev": 0.08},
        "military_pressure":    {"mean": 0.25, "stddev": 0.08},
        "economic_stress":      {"mean": 0.25, "stddev": 0.08},
        "diplomatic_isolation": {"mean": 0.10, "stddev": 0.05},
        "internal_stability":   {"mean": 0.20, "stddev": 0.08},
    },
    "FRA": {
        "conflict_activity":    {"mean": 0.20, "stddev": 0.08},
        "military_pressure":    {"mean": 0.30, "stddev": 0.08},
        "economic_stress":      {"mean": 0.25, "stddev": 0.08},
        "diplomatic_isolation": {"mean": 0.10, "stddev": 0.05},
        "internal_stability":   {"mean": 0.25, "stddev": 0.10},
    },
    "BRA": {
        "conflict_activity":    {"mean": 0.15, "stddev": 0.08},
        "military_pressure":    {"mean": 0.10, "stddev": 0.05},
        "economic_stress":      {"mean": 0.40, "stddev": 0.12},
        "diplomatic_isolation": {"mean": 0.15, "stddev": 0.05},
        "internal_stability":   {"mean": 0.35, "stddev": 0.10},
    },
    "TUR": {
        "conflict_activity":    {"mean": 0.45, "stddev": 0.12},
        "military_pressure":    {"mean": 0.50, "stddev": 0.10},
        "economic_stress":      {"mean": 0.50, "stddev": 0.12},
        "diplomatic_isolation": {"mean": 0.35, "stddev": 0.10},
        "internal_stability":   {"mean": 0.40, "stddev": 0.12},
    },
    "SAU": {
        "conflict_activity":    {"mean": 0.35, "stddev": 0.12},
        "military_pressure":    {"mean": 0.45, "stddev": 0.10},
        "economic_stress":      {"mean": 0.25, "stddev": 0.08},
        "diplomatic_isolation": {"mean": 0.35, "stddev": 0.10},
        "internal_stability":   {"mean": 0.30, "stddev": 0.08},
    },
}

# Default baseline for countries not in the table
DEFAULT_BASELINE: Dict[str, Dict[str, float]] = {
    "conflict_activity":    {"mean": 0.30, "stddev": 0.15},
    "military_pressure":    {"mean": 0.30, "stddev": 0.15},
    "economic_stress":      {"mean": 0.35, "stddev": 0.15},
    "diplomatic_isolation": {"mean": 0.30, "stddev": 0.15},
    "internal_stability":   {"mean": 0.35, "stddev": 0.15},
}


# =====================================================================
# Anomaly Result
# =====================================================================

@dataclass
class AnomalyResult:
    """
    Result of comparing observed behavior against baseline.
    """
    country: str
    dimension: str
    observed: float
    baseline_mean: float
    baseline_stddev: float
    z_score: float              # Standard deviations from baseline
    anomaly_level: str          # "normal", "elevated", "significant", "extreme"
    direction: str              # "above" or "below" baseline
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "country": self.country,
            "dimension": self.dimension,
            "observed": round(self.observed, 4),
            "baseline_mean": round(self.baseline_mean, 4),
            "baseline_stddev": round(self.baseline_stddev, 4),
            "z_score": round(self.z_score, 2),
            "anomaly_level": self.anomaly_level,
            "direction": self.direction,
            "description": self.description,
        }


# =====================================================================
# Baseline Model
# =====================================================================

class BaselineModel:
    """
    Evaluates whether observed behavior is NORMAL for a specific country.

    Usage:
        model = BaselineModel()

        # Check single dimension
        result = model.check(country="CHE", dimension="conflict_activity", observed=0.50)
        # → AnomalyResult(z_score=15.0, anomaly_level="extreme")

        result = model.check(country="ISR", dimension="conflict_activity", observed=0.65)
        # → AnomalyResult(z_score=0.0, anomaly_level="normal")

        # Check all dimensions for a country
        results = model.check_all(country="CHE", observed_scores={
            "conflict_activity": 0.50,
            "military_pressure": 0.10,
        })
    """

    def __init__(self, baselines: Dict = None):
        self.baselines = baselines or COUNTRY_BASELINES

    def check(
        self,
        country: str,
        dimension: str,
        observed: float,
    ) -> AnomalyResult:
        """
        Check if observed behavior is anomalous for this country.

        Args:
            country: ISO3 country code
            dimension: One of the 5 dimension names
            observed: Observed score (0.0—1.0)

        Returns:
            AnomalyResult with z-score and classification
        """
        country = country.upper()
        baseline = self.baselines.get(country, DEFAULT_BASELINE)
        dim_baseline = baseline.get(dimension, DEFAULT_BASELINE.get(dimension, {"mean": 0.3, "stddev": 0.15}))

        mean = dim_baseline["mean"]
        stddev = dim_baseline["stddev"]

        # Prevent division by zero
        if stddev < 0.001:
            stddev = 0.001

        # z-score
        z = (observed - mean) / stddev
        abs_z = abs(z)

        # Direction
        direction = "above" if z > 0 else "below"

        # Classification
        if abs_z < 1.0:
            level = "normal"
        elif abs_z < 2.0:
            level = "elevated"
        elif abs_z < 3.0:
            level = "significant"
        else:
            level = "extreme"

        # Description
        desc = (
            f"{country} '{dimension}' at {observed:.2f} "
            f"({level} - {abs_z:.1f}sigma {direction} baseline of {mean:.2f})"
        )

        return AnomalyResult(
            country=country,
            dimension=dimension,
            observed=observed,
            baseline_mean=mean,
            baseline_stddev=stddev,
            z_score=round(z, 4),
            anomaly_level=level,
            direction=direction,
            description=desc,
        )

    def check_all(
        self,
        country: str,
        observed_scores: Dict[str, float],
    ) -> List[AnomalyResult]:
        """
        Check all provided dimensions against baseline.

        Args:
            country: ISO3 country code
            observed_scores: {dimension_name: observed_score}

        Returns:
            List of AnomalyResult, one per dimension
        """
        results = []
        for dim, score in observed_scores.items():
            results.append(self.check(country, dim, score))
        return results

    def get_anomalies_only(
        self,
        country: str,
        observed_scores: Dict[str, float],
        min_level: str = "elevated",
    ) -> List[AnomalyResult]:
        """Return only anomalous dimensions (filtering out normal behavior)."""
        level_order = {"normal": 0, "elevated": 1, "significant": 2, "extreme": 3}
        min_rank = level_order.get(min_level, 1)

        results = self.check_all(country, observed_scores)
        return [r for r in results if level_order.get(r.anomaly_level, 0) >= min_rank]

    def get_baseline(self, country: str) -> Dict[str, Dict[str, float]]:
        """Get the baseline for a country (or default)."""
        return self.baselines.get(country.upper(), DEFAULT_BASELINE)

    def has_baseline(self, country: str) -> bool:
        """Check if we have a calibrated baseline for this country."""
        return country.upper() in self.baselines

    def list_calibrated_countries(self) -> List[str]:
        """List all countries with calibrated baselines."""
        return sorted(self.baselines.keys())


# =====================================================================
# Module-Level Singleton
# =====================================================================

baseline_model = BaselineModel()

__all__ = [
    "BaselineModel", "baseline_model",
    "AnomalyResult",
    "COUNTRY_BASELINES", "DEFAULT_BASELINE",
]
