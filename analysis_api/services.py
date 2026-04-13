"""
Analysis Engine - Core Intelligence Logic
=========================================
Connects the API to the Layer-3 State Builder.

Design Principle:
    This module is the ONLY bridge between the API (what MoltBot sees)
    and the Intelligence Engine (what computes truth).
    MoltBot never imports Layer2 or Layer3 directly.
"""

from typing import Dict, List, Optional
import datetime
import json
import os

# Import Layer-3 Builder (the analytical brain)
from engine.Layer3_StateModel.construction.country_state_builder import CountryStateBuilder
from engine.Layer3_StateModel.country_state_schema import CountryStateVector
from Core.orchestrator.analysis_router import analysis_router, AnalysisType

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE, "data", "tension_history.json")


class AnalysisEngine:
    """
    Central engine for geopolitical analysis.
    Exposes Layer-3 intelligence to the API layer.
    """

    def __init__(self):
        self.builder = CountryStateBuilder()
        self.router = analysis_router

    def get_country_profile(self, country_code: str, date: str = None) -> Dict:
        """
        Build a FULL CountryStateVector and return it as a dict.
        This is the primary intelligence endpoint.
        """
        vector = self.builder.build(country_code, date)
        return vector.to_dict()

    def get_country_tension(self, country_code: str) -> Dict:
        """
        Backward-compatible tension endpoint.
        Uses the builder for real computation now.
        """
        vector = self.builder.build(country_code)
        return {
            "country": vector.country_code,
            "tension_score": vector.tension_index,
            "trend": "escalating" if vector.escalation_risk > 0.4 else "stable",
            "conflict_events": vector.conflict_activity.value,
            "cooperation_events": 1.0 - vector.diplomatic_isolation.value,
            "major_actors": vector.signal_breakdown.get("conflict", {}).get("sources", []),
            "risk_level": vector.overall_risk_level.value,
            "last_updated": vector.last_updated,
        }

    def analyze(self, country_code: str, analysis_type: str) -> Dict:
        """
        Perform a specific type of analysis.
        Routes to the correct signals and weights.
        """
        # Parse analysis type
        try:
            atype = AnalysisType(analysis_type)
        except ValueError:
            atype = AnalysisType.FULL_PROFILE

        route = self.router.get_route(atype)
        vector = self.builder.build(country_code)

        # Extract only the relevant dimensions
        result = {
            "country": vector.country_code,
            "analysis_type": atype.value,
            "description": route["description"],
            "dimensions": {},
            "composite_score": vector.tension_index,
            "risk_level": vector.overall_risk_level.value,
            "analysis_confidence": vector.signal_breakdown.get("validation_confidence", {}),
            "intent_capability": vector.signal_breakdown.get("intent_capability", {}),
            "baseline_anomalies": vector.signal_breakdown.get("baseline_anomalies", []),
            "required_sources": route["required_sources"],
            "available_sources": list(vector.evidence_sources.keys()),
            "missing_sources": [
                s for s in route["required_sources"]
                if s not in vector.evidence_sources
            ],
        }

        # Add relevant dimensions
        for dim_name in route["primary_dimensions"]:
            dim = vector.get_dimension(dim_name)
            if dim:
                result["dimensions"][dim_name] = dim.to_dict()

        return result

    def get_history(self, country_code: str) -> List[Dict]:
        """Get tension history for charting."""
        if os.path.exists(DATA_PATH):
            try:
                with open(DATA_PATH, "r") as f:
                    history_cache = json.load(f)
            except Exception:
                history_cache = {}
        else:
            history_cache = {}

        history = []
        for date, date_data in sorted(history_cache.items()):
            entries = date_data.get(country_code.upper(), [])
            for entry in entries:
                history.append({
                    "date": date,
                    "time": entry.get("time", "00:00"),
                    "tension": entry["tension"],
                })
        return history

    def get_dimension_timeline(
        self,
        country_code: str,
        dimension: str,
        limit: int = 30,
    ) -> List[Dict]:
        """
        Return per-date dimension values with supporting evidence metadata.
        """
        normalized = (dimension or "").strip().lower()
        valid_dimensions = {
            "military_pressure",
            "economic_stress",
            "diplomatic_isolation",
            "internal_stability",
            "conflict_activity",
        }
        if normalized not in valid_dimensions:
            raise ValueError(f"Unsupported dimension: {dimension}")

        dates = self._get_country_dates(country_code, max_points=limit)
        timeline = []
        for date in dates:
            vector = self.builder.build(country_code, date)
            dim = vector.get_dimension(normalized)
            if dim is None:
                continue
            timeline.append(
                {
                    "date": date,
                    "dimension": normalized,
                    "value": round(dim.value, 4),
                    "confidence": round(dim.confidence, 4),
                    "sources": list(dim.contributing_sources),
                    "freshness": dim.last_data_date,
                    "explanation": dim.explanation,
                }
            )
        return timeline

    def get_confidence_timeline(self, country_code: str, limit: int = 30) -> List[Dict]:
        """
        Return confidence evolution and short reason codes for changes.
        """
        dates = self._get_country_dates(country_code, max_points=limit)
        timeline: List[Dict] = []
        previous: Optional[Dict] = None

        for date in dates:
            vector = self.builder.build(country_code, date)
            confidence = vector.signal_breakdown.get("validation_confidence", {})

            current = {
                "date": date,
                "score": round(float(confidence.get("overall_score", 0.0) or 0.0), 4),
                "level": confidence.get("level", "UNKNOWN"),
                "observation_count": int(confidence.get("observation_count", 0) or 0),
                "source_count": int(confidence.get("source_count", 0) or 0),
                "contradiction_count": int(confidence.get("contradiction_count", 0) or 0),
                "warnings": confidence.get("warnings", []),
            }

            if previous is None:
                current["delta"] = 0.0
                current["reason"] = ["baseline"]
            else:
                current["delta"] = round(current["score"] - previous["score"], 4)
                current["reason"] = self._explain_confidence_change(previous, current)

            timeline.append(current)
            previous = current

        return timeline

    def _get_country_dates(self, country_code: str, max_points: int = 30) -> List[str]:
        history = self.get_history(country_code)
        unique_dates = sorted({point["date"] for point in history if point.get("date")})
        if not unique_dates:
            return [datetime.datetime.now().strftime("%Y-%m-%d")]
        max_points = max(1, int(max_points))
        return unique_dates[-max_points:]

    def _explain_confidence_change(self, previous: Dict, current: Dict) -> List[str]:
        reasons: List[str] = []
        if current["observation_count"] > previous["observation_count"]:
            reasons.append("more_observations")
        elif current["observation_count"] < previous["observation_count"]:
            reasons.append("fewer_observations")

        if current["source_count"] > previous["source_count"]:
            reasons.append("broader_source_coverage")
        elif current["source_count"] < previous["source_count"]:
            reasons.append("narrower_source_coverage")

        if current["contradiction_count"] > previous["contradiction_count"]:
            reasons.append("more_contradictions")
        elif current["contradiction_count"] < previous["contradiction_count"]:
            reasons.append("fewer_contradictions")

        if not reasons:
            reasons.append("score_model_shift")
        return reasons


# Singleton
engine = AnalysisEngine()
