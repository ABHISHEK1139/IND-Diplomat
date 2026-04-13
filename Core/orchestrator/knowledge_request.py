"""
Knowledge Request Loop — The "I Don't Know" Protocol
======================================================
Layer 3's mechanism for ADMITTING IGNORANCE.

Without this:
    Builder silently returns 0.5 defaults when data is missing.
    Layer 4 sees "moderate tension" when reality is:
    "We have NO DATA for this country's military posture."

With this:
    Builder reports EXACTLY what it knows and what it lacks.
    L4 can say: "Assessment has LOW CONFIDENCE because SIPRI data missing."
    Controller can trigger targeted collection to fill the gap.

Design decisions:
    - KnowledgeGap is a structured request, not free text
    - Gaps are prioritized so collection runs critical gaps first
    - Builder returns (result, gaps) tuple — never hides ignorance
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger("knowledge_request")


# =====================================================================
# Gap Types — What kind of information is missing
# =====================================================================

class GapType(Enum):
    """Taxonomy of knowledge gaps."""
    MISSING_SOURCE       = "missing_source"       # No data from this source at all
    STALE_DATA           = "stale_data"            # Data exists but is too old
    LOW_CONFIDENCE       = "low_confidence"        # Data exists but trust is low
    MISSING_DIMENSION    = "missing_dimension"     # Entire dimension has no inputs
    CONFLICTING_SOURCES  = "conflicting_sources"   # Sources disagree significantly
    MISSING_ENTITY       = "missing_entity"        # Actor not in entity registry
    MISSING_RELATIONSHIP = "missing_relationship"  # No graph link between known entities


class GapPriority(Enum):
    """How urgently this gap needs to be filled."""
    CRITICAL   = "critical"    # Assessment is unreliable without this
    IMPORTANT  = "important"   # Significantly affects accuracy
    DESIRABLE  = "desirable"   # Would improve confidence but not essential


# =====================================================================
# Knowledge Gap — A structured "I need this" request
# =====================================================================

@dataclass
class KnowledgeGap:
    """
    Describes a specific piece of missing knowledge.

    This is what Layer 3 produces when it can't compute a dimension
    with sufficient confidence.
    """
    gap_type: GapType
    priority: GapPriority
    country: str                            # Which country/entity
    dimension: str                          # Which dimension is affected
    missing_source: str = ""                # Which source is needed
    description: str = ""                   # Human-readable explanation
    suggested_action: str = ""              # What to do about it
    timeframe: str = ""                     # What time range is needed
    impact: str = ""                        # How this affects the assessment
    created_at: str = ""                    # When this gap was identified

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_type": self.gap_type.value,
            "priority": self.priority.value,
            "country": self.country,
            "dimension": self.dimension,
            "missing_source": self.missing_source,
            "description": self.description,
            "suggested_action": self.suggested_action,
            "timeframe": self.timeframe,
            "impact": self.impact,
            "created_at": self.created_at,
        }


# =====================================================================
# Assessment Confidence — Meta-judgment on the overall result
# =====================================================================

class ConfidenceLevel(Enum):
    """Overall confidence in an assessment."""
    HIGH           = "high"            # Multiple sources, recent data, consensus
    MODERATE       = "moderate"        # Some gaps but core dimensions covered
    LOW            = "low"             # Major gaps, assessment is speculative
    INSUFFICIENT   = "insufficient"    # Too many gaps — should not be used for decisions


@dataclass
class AssessmentConfidence:
    """
    Meta-judgment: How much should Layer 4 trust this assessment?

    This wraps the CountryStateVector to say:
    "Here's our best guess, but here's what's missing."
    """
    overall_level: ConfidenceLevel
    dimensions_covered: int                 # Out of 5
    dimensions_with_data: int               # Have real data (not defaults)
    sources_available: List[str] = field(default_factory=list)
    sources_missing: List[str] = field(default_factory=list)
    gaps: List[KnowledgeGap] = field(default_factory=list)
    critical_gap_count: int = 0
    total_data_points: int = 0
    freshest_data: str = ""                 # Date of most recent data
    stalest_data: str = ""                  # Date of oldest data used
    explanation: str = ""                   # Why this confidence level

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_level": self.overall_level.value,
            "dimensions_covered": self.dimensions_covered,
            "dimensions_with_data": self.dimensions_with_data,
            "sources_available": self.sources_available,
            "sources_missing": self.sources_missing,
            "gaps": [g.to_dict() for g in self.gaps],
            "critical_gap_count": self.critical_gap_count,
            "total_data_points": self.total_data_points,
            "freshest_data": self.freshest_data,
            "stalest_data": self.stalest_data,
            "explanation": self.explanation,
        }


# =====================================================================
# Gap Detector — Analyses what's missing from a signal set
# =====================================================================

# What sources SHOULD feed each dimension (ideal state)
DIMENSION_EXPECTED_SOURCES: Dict[str, List[str]] = {
    "conflict_activity":     ["gdelt", "acled"],
    "military_pressure":     ["sipri", "gdelt"],
    "economic_stress":       ["world_bank", "un_comtrade", "imf"],
    "diplomatic_isolation":  ["atop", "gdelt", "treaties"],
    "internal_stability":    ["v_dem", "gdelt"],
}

# Minimum required sources per dimension for HIGH confidence
MIN_SOURCES_HIGH_CONFIDENCE = 2
# Below this → INSUFFICIENT
MIN_SOURCES_ANY_CONFIDENCE = 1


class GapDetector:
    """
    Inspects the signals available for a country and identifies
    what's missing before the builder runs.

    Usage:
        detector = GapDetector()
        gaps, confidence = detector.analyze(
            country="IND",
            available_signals={"gdelt": {...}},
            date="2026-02-15"
        )
    """

    def analyze(
        self,
        country: str,
        available_signals: Dict[str, Any],
        date: str = "",
    ) -> Tuple[List[KnowledgeGap], AssessmentConfidence]:
        """
        Analyze available signals and return gaps + confidence assessment.

        Args:
            country: ISO3 country code
            available_signals: Dict of source_name → signal data
            date: Assessment date

        Returns:
            (gaps, confidence) tuple
        """
        gaps: List[KnowledgeGap] = []
        available_sources = set(available_signals.keys())
        all_expected = set()
        dimensions_covered = 0
        dimensions_with_data = 0

        for dimension, expected_sources in DIMENSION_EXPECTED_SOURCES.items():
            all_expected.update(expected_sources)
            dim_available = [s for s in expected_sources if s in available_sources]

            if dim_available:
                dimensions_covered += 1
                dimensions_with_data += 1
            else:
                dimensions_covered += 1  # We can compute with defaults
                # Flag the gap
                gaps.append(KnowledgeGap(
                    gap_type=GapType.MISSING_DIMENSION,
                    priority=GapPriority.CRITICAL,
                    country=country,
                    dimension=dimension,
                    missing_source=", ".join(expected_sources),
                    description=(
                        f"No data sources available for '{dimension}'. "
                        f"Expected: {expected_sources}. Builder will use defaults."
                    ),
                    suggested_action=f"Run {expected_sources[0]} sensor for {country}",
                    timeframe=f"Last 30 days from {date}" if date else "Recent",
                    impact=f"'{dimension}' dimension will be estimated, not observed",
                ))

            # Check for specific missing sources  
            for src in expected_sources:
                if src not in available_sources:
                    if not any(g.missing_source == src and g.dimension == dimension
                               for g in gaps):
                        gaps.append(KnowledgeGap(
                            gap_type=GapType.MISSING_SOURCE,
                            priority=(GapPriority.IMPORTANT
                                      if dim_available else GapPriority.CRITICAL),
                            country=country,
                            dimension=dimension,
                            missing_source=src,
                            description=f"'{src}' data not available for {country}",
                            suggested_action=f"Collect {src} data for {country}",
                            timeframe=f"Last 30 days from {date}" if date else "Recent",
                            impact=f"Reduces confidence in '{dimension}' dimension",
                        ))

        # Compute overall confidence
        missing_sources = list(all_expected - available_sources)
        critical_gaps = [g for g in gaps if g.priority == GapPriority.CRITICAL]

        if dimensions_with_data == 0:
            level = ConfidenceLevel.INSUFFICIENT
            explanation = "No real data available for any dimension. All values are defaults."
        elif len(critical_gaps) >= 3:
            level = ConfidenceLevel.LOW
            explanation = f"{len(critical_gaps)} critical gaps. Assessment is speculative."
        elif len(critical_gaps) >= 1:
            level = ConfidenceLevel.MODERATE
            explanation = (
                f"{dimensions_with_data}/5 dimensions have data. "
                f"{len(critical_gaps)} critical gap(s) remain."
            )
        else:
            level = ConfidenceLevel.HIGH
            explanation = f"All dimensions have data from {dimensions_with_data} sources."

        confidence = AssessmentConfidence(
            overall_level=level,
            dimensions_covered=dimensions_covered,
            dimensions_with_data=dimensions_with_data,
            sources_available=sorted(available_sources),
            sources_missing=sorted(missing_sources),
            gaps=gaps,
            critical_gap_count=len(critical_gaps),
            total_data_points=sum(1 for _ in available_signals.values()),
            freshest_data=date,
            explanation=explanation,
        )

        if gaps:
            logger.info(
                f"[{country}] {len(gaps)} knowledge gaps detected. "
                f"Confidence: {level.value}"
            )

        return gaps, confidence


# =====================================================================
# Module-Level Singleton
# =====================================================================

gap_detector = GapDetector()


__all__ = [
    "KnowledgeGap",
    "GapType",
    "GapPriority",
    "AssessmentConfidence",
    "ConfidenceLevel",
    "GapDetector",
    "gap_detector",
    "DIMENSION_EXPECTED_SOURCES",
]
