"""
Politiq AI — Research Engine Schemas
====================================

Defines all core data models flowing through the Research Platform:
ResearchRequest -> SearchResult -> Document -> Evidence -> ResearchResult
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class ResearchRequest(BaseModel):
    """A parameterized request for the research platform."""
    id: str = Field(..., description="Unique identifier for this research request")
    topic: str = Field(..., description="Broad topic of the research")
    queries: List[str] = Field(..., description="Specific search queries to execute")
    countries: List[str] = Field(default_factory=list, description="Target countries to focus on")
    languages: List[str] = Field(default_factory=lambda: ["en"], description="Preferred languages")
    date_range: Optional[str] = Field(None, description="e.g., 'last 30 days', '2023-2024'")
    required_sources: List[str] = Field(default_factory=list, description="Providers to force (e.g. 'gdelt', 'duckduckgo')")
    excluded_sources: List[str] = Field(default_factory=list, description="Providers to ignore")
    news_only: bool = Field(False, description="Restrict to news sources")
    academic_only: bool = Field(False, description="Restrict to academic sources (Arxiv, etc)")
    government_only: bool = Field(False, description="Restrict to official govt domains (.gov, etc)")
    min_confidence: float = Field(0.5, description="Minimum confidence threshold for returning evidence")
    max_results: int = Field(10, description="Max results per query")
    priority: str = Field("normal", description="high, normal, low")
    timeout: int = Field(60, description="Max execution time in seconds")


class SearchResult(BaseModel):
    """Raw result returned by a SearchProvider."""
    title: str
    url: str
    snippet: str
    source: str
    published_date: Optional[datetime] = None
    language: Optional[str] = None
    score: float = 1.0


class Document(BaseModel):
    """A crawled and extracted document (intermediate representation)."""
    title: str
    url: str
    html: Optional[str] = None
    clean_text: str
    language: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    chunks: List[str] = Field(default_factory=list)


class Evidence(BaseModel):
    """Verified, structured knowledge derived from a Document."""
    title: str
    url: str
    publisher: str
    published_date: Optional[datetime] = None
    country: Optional[str] = None
    reliability_score: float = Field(0.0, description="0.0 to 1.0")
    bias_score: float = Field(0.0, description="-1.0 (extreme left/anti) to +1.0 (extreme right/pro), 0 is neutral")
    confidence: float = Field(0.0, description="0.0 to 1.0")
    cameo_code: Optional[str] = Field(None, description="CAMEO conflict code if applicable")
    language: Optional[str] = None
    text: str = Field(..., description="The verified text content/snippet")


class ResearchResult(BaseModel):
    """Final payload returned by the Research Planner."""
    documents: List[Document] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    coverage: float = Field(0.0, description="Percentage of original queries answered")
    confidence: float = Field(0.0, description="Overall confidence of the findings")
    failed_queries: List[str] = Field(default_factory=list)
    execution_time: float = 0.0
    sources_used: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
