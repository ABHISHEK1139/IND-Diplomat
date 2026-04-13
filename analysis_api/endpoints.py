"""
Analysis API Endpoints
======================
REST API that exposes the Intelligence Engine to MoltBot.

Design Principle:
    MoltBot calls THESE endpoints.
    MoltBot NEVER imports Layer2 or Layer3 directly.
    Every response is structured, traceable JSON.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

from .services import engine

router = APIRouter()


# ── Response Models ──────────────────────────────────────────────

class TensionResponse(BaseModel):
    country: str
    tension_score: float
    trend: str
    conflict_events: float
    cooperation_events: float
    major_actors: List[str]
    risk_level: str
    last_updated: str

class TensionHistoryPoint(BaseModel):
    date: str
    time: str
    tension: float

class AnalysisRequest(BaseModel):
    country: str
    analysis_type: str  # "war_risk", "economic_pressure", etc.

class AnalysisResponse(BaseModel):
    country: str
    analysis_type: str
    description: str
    dimensions: Dict
    composite_score: float
    risk_level: str
    analysis_confidence: Dict = Field(default_factory=dict)
    intent_capability: Dict = Field(default_factory=dict)
    baseline_anomalies: List[Dict] = Field(default_factory=list)
    required_sources: List[str]
    available_sources: List[str]
    missing_sources: List[str]

class DimensionTimelinePoint(BaseModel):
    date: str
    dimension: str
    value: float
    confidence: float
    sources: List[str]
    freshness: str
    explanation: str

class ConfidenceTimelinePoint(BaseModel):
    date: str
    score: float
    level: str
    delta: float
    observation_count: int
    source_count: int
    contradiction_count: int
    warnings: List[str]
    reason: List[str]


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/tension/{country_code}", response_model=TensionResponse)
def get_country_tension(country_code: str):
    """Get the current geopolitical tension score for a country."""
    try:
        data = engine.get_country_tension(country_code)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tension/{country_code}/history", response_model=List[TensionHistoryPoint])
def get_country_history(country_code: str):
    """Get historical tension data for charting."""
    try:
        return engine.get_history(country_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/country/{country_code}/profile")
def get_country_profile(country_code: str):
    """
    Get the FULL CountryStateVector for a country.
    This is the primary intelligence endpoint.
    Returns all 5 dimensions, 3 composite indices, and evidence trail.
    """
    try:
        return engine.get_country_profile(country_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=AnalysisResponse)
def analyze(request: AnalysisRequest):
    """
    Perform a specific type of analysis on a country.
    Routes to the correct signals and weights.
    """
    try:
        return engine.analyze(request.country, request.analysis_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/country/{country_code}/timeline/{dimension}",
    response_model=List[DimensionTimelinePoint],
)
def get_dimension_timeline(country_code: str, dimension: str, limit: int = 30):
    """Dimension-by-date timeline with source and confidence metadata."""
    try:
        return engine.get_dimension_timeline(country_code, dimension, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/country/{country_code}/confidence-history",
    response_model=List[ConfidenceTimelinePoint],
)
def get_confidence_history(country_code: str, limit: int = 30):
    """Explain why confidence changed over time."""
    try:
        return engine.get_confidence_timeline(country_code, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
