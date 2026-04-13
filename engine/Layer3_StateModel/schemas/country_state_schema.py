"""
Country State Schema — The Analytical Vector
=============================================
This is the SINGLE SOURCE OF TRUTH for what a country profile looks like.

Every country, at every point in time, gets ONE of these objects.
This is what the Analysis API serves and what MoltBot reads.

Design Principle:
    Raw data → Signals (Layer-2) → THIS VECTOR (Layer-3) → MoltBot (Layer-4)
    The LLM NEVER sees raw data. It only sees this vector.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class RiskLevel(Enum):
    """Categorical risk assessment."""
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DimensionScore:
    """
    A single analytical dimension with its score, confidence, and evidence trail.
    This is NOT raw data — it is a COMPUTED assessment.
    """
    value: float                     # 0.0 to 1.0 (normalized score)
    confidence: float                # 0.0 to 1.0 (how much data backs this)
    contributing_sources: List[str]  # e.g., ["GDELT", "SIPRI"]
    last_data_date: str              # When the freshest contributing data was from
    explanation: str                 # One-line human-readable explanation

    def to_dict(self) -> Dict:
        return {
            "value": round(self.value, 4),
            "confidence": round(self.confidence, 2),
            "sources": self.contributing_sources,
            "freshness": self.last_data_date,
            "explanation": self.explanation
        }


@dataclass
class CountryStateVector:
    """
    The computed analytical profile of a country at a point in time.

    This is NOT a database record.
    This is a RESEARCH CONCLUSION, built by combining multiple signals
    with trust weights and analytical formulas.

    Fields:
        country_code: ISO 3166-1 alpha-3 (e.g., "IND", "CHN")
        date: Assessment date (YYYY-MM-DD)

        # ── 5 Computed Dimensions ──
        military_pressure:     How active/threatening the military posture is
        economic_stress:       Vulnerability to economic pressure or crisis
        diplomatic_isolation:  How cut off from alliances/partners
        internal_stability:    Regime stability and domestic cohesion
        conflict_activity:     Active hostilities (events-based)

        # ── 3 Composite Indices ──
        tension_index:   Weighted composite of all dimensions
        stability_index: Inverse of overall risk
        escalation_risk: Forward-looking risk estimate

        # ── Evidence Trail ──
        evidence_sources: Which sources contributed and their confidence
        signal_breakdown: Per-signal summary data (for debugging/traceability)
    """

    # ── Identity ──
    country_code: str
    date: str

    # ── 5 Analytical Dimensions ──
    military_pressure: DimensionScore
    economic_stress: DimensionScore
    diplomatic_isolation: DimensionScore
    internal_stability: DimensionScore
    conflict_activity: DimensionScore

    # ── 3 Composite Indices ──
    tension_index: float          # 0.0 (calm) to 1.0 (crisis)
    stability_index: float        # 0.0 (failed state) to 1.0 (rock solid)
    escalation_risk: float        # 0.0 (de-escalating) to 1.0 (imminent)

    # ── Categorical Assessment ──
    overall_risk_level: RiskLevel

    # ── Evidence Trail ──
    evidence_sources: Dict[str, float] = field(default_factory=dict)
    signal_breakdown: Dict[str, Dict] = field(default_factory=dict)
    data_freshness: Dict[str, str] = field(default_factory=dict)
    last_updated: str = ""
    legal_rhetoric_trend: str = "stable"
    legal_rhetoric_shift: float = 0.0
    recent_activity_signals: int = 0

    def to_dict(self) -> Dict:
        """Serialize for API response."""
        return {
            "country": self.country_code,
            "date": self.date,
            "dimensions": {
                "military_pressure": self.military_pressure.to_dict(),
                "economic_stress": self.economic_stress.to_dict(),
                "diplomatic_isolation": self.diplomatic_isolation.to_dict(),
                "internal_stability": self.internal_stability.to_dict(),
                "conflict_activity": self.conflict_activity.to_dict(),
            },
            "indices": {
                "tension_index": round(self.tension_index, 4),
                "stability_index": round(self.stability_index, 4),
                "escalation_risk": round(self.escalation_risk, 4),
            },
            "risk_level": self.overall_risk_level.value,
            "legal_rhetoric_trend": self.legal_rhetoric_trend,
            "legal_trend": self.legal_rhetoric_trend,
            "legal_rhetoric_shift": round(self.legal_rhetoric_shift, 4),
            "recent_activity_signals": int(self.recent_activity_signals),
            "evidence": self.evidence_sources,
            "analysis_confidence": self.signal_breakdown.get("validation_confidence", {}),
            "intent_capability": self.signal_breakdown.get("intent_capability", {}),
            "baseline_anomalies": self.signal_breakdown.get("baseline_anomalies", []),
            "data_freshness": self.data_freshness,
            "last_updated": self.last_updated,
        }

    def get_dimension(self, name: str) -> Optional[DimensionScore]:
        """Get a dimension by name."""
        return getattr(self, name, None)

    def __repr__(self):
        return (
            f"<CountryStateVector({self.country_code}, {self.date}) "
            f"tension={self.tension_index:.2f} "
            f"stability={self.stability_index:.2f} "
            f"risk={self.overall_risk_level.value}>"
        )
