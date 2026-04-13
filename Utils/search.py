"""
Reputational Filter for Trusted Internet Search
=================================================
Ensures search results come only from reputable, verified sources.

Features:
1. Domain Allow-List - Only trusted .gov, .org, international bodies
2. Source Reliability Score - Based on domain rank and citation frequency
3. Automatic Filtering - Discard sources below threshold before MCTS reasoning
4. Maximum Trusted Sources - Limit to 100 verified sources

Real-World Use:
An industrial giant uses IND-Diplomat for a ₹5,000 crore decision.
Every source must be legally defensible and verifiable.
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DomainTier(Enum):
    """Trust tiers for domains."""
    TIER_1_GOVERNMENT = 1      # .gov domains - highest trust
    TIER_2_INTERNATIONAL = 2   # UN, WTO, World Bank
    TIER_3_ACADEMIC = 3        # .edu, research institutions
    TIER_4_MAJOR_NEWS = 4      # Reuters, AP, established media
    TIER_5_VERIFIED = 5        # Manually verified sources
    UNTRUSTED = 99             # Unknown/untrusted


@dataclass
class SourceReliabilityScore:
    """Reliability score for a source."""
    url: str
    domain: str
    tier: DomainTier
    base_score: float
    citation_boost: float = 0.0
    recency_boost: float = 0.0
    final_score: float = 0.0
    
    def calculate(self) -> float:
        """Calculate final reliability score."""
        # Base score from tier (0.5-1.0)
        tier_scores = {
            DomainTier.TIER_1_GOVERNMENT: 1.0,
            DomainTier.TIER_2_INTERNATIONAL: 0.95,
            DomainTier.TIER_3_ACADEMIC: 0.85,
            DomainTier.TIER_4_MAJOR_NEWS: 0.75,
            DomainTier.TIER_5_VERIFIED: 0.70,
            DomainTier.UNTRUSTED: 0.0
        }
        
        self.base_score = tier_scores.get(self.tier, 0.0)
        self.final_score = min(1.0, self.base_score + self.citation_boost + self.recency_boost)
        return self.final_score


@dataclass
class FilteredSearchResult:
    """A search result that passed reputation filter."""
    url: str
    title: str
    content: str
    reliability_score: SourceReliabilityScore
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReputationalSearch:
    """
    Reputational Filter for Internet Search.
    
    Only returns results from trusted, verified sources.
    Implements domain allow-listing and reliability scoring.
    """
    
    # Maximum trusted sources to consider
    MAX_TRUSTED_SOURCES = 100
    
    # Minimum reliability score to pass filter
    MIN_RELIABILITY_THRESHOLD = 0.6
    
    # === DOMAIN ALLOW-LISTS ===
    
    # Tier 1: Government Domains (Highest Trust)
    TIER_1_DOMAINS = {
        # India Government
        ".gov.in", "mea.gov.in", "pib.gov.in", "india.gov.in",
        "commerce.gov.in", "dgft.gov.in", "cbic.gov.in", "rbi.org.in",
        "dipp.gov.in", "makeinindia.com", "investindia.gov.in",
        # Other Governments
        ".gov", ".gov.uk", ".gov.au", ".gc.ca"
    }
    
    # Tier 2: International Organizations
    TIER_2_DOMAINS = {
        # United Nations
        "un.org", "undp.org", "unido.org", "unctad.org",
        "unescap.org", "unicef.org", "unhcr.org",
        # Trade Organizations
        "wto.org", "worldbank.org", "imf.org", "ifc.org",
        "adb.org", "aiib.org", "brics-info.org",
        # Regional Bodies
        "asean.org", "saarc-sec.org", "bimstec.org", "iora.int",
        # Legal/Standards
        "icj-cij.org", "icc-ccs.org", "iso.org"
    }
    
    # Tier 3: Academic & Research
    TIER_3_DOMAINS = {
        ".edu", ".ac.in", ".ac.uk", ".edu.au",
        "orfonline.org", "brookings.edu", "carnegieendowment.org",
        "cfr.org", "rand.org", "chathamhouse.org",
        "idsa.in", "icrier.org", "nipfp.org.in"
    }
    
    # Tier 4: Major News (Established, Fact-Checked)
    TIER_4_DOMAINS = {
        "reuters.com", "ap.news", "bbc.com", "bbc.co.uk",
        "thehindu.com", "economictimes.com", "livemint.com",
        "ft.com", "economist.com", "wsj.com"
    }
    
    # Tier 5: Verified Business Sources
    TIER_5_DOMAINS = {
        "trademap.org", "intracen.org", "comtrade.un.org",
        "tradeeconomics.com", "statista.com"
    }
    
    # === DENY-LIST (Explicitly Blocked) ===
    DENIED_DOMAINS = {
        "wikipedia.org",  # Too editable
        "quora.com",      # User-generated
        "reddit.com",     # User-generated
        "medium.com",     # Mixed quality
        "blogspot.com",   # Blogs
        "wordpress.com"   # Blogs
    }
    
    def __init__(self):
        self._all_allowed = (
            self.TIER_1_DOMAINS | 
            self.TIER_2_DOMAINS | 
            self.TIER_3_DOMAINS | 
            self.TIER_4_DOMAINS |
            self.TIER_5_DOMAINS
        )
    
    def classify_domain(self, url: str) -> Tuple[str, DomainTier]:
        """Classify a URL by its domain tier."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www prefix
            if domain.startswith("www."):
                domain = domain[4:]
            
            # Check deny list first
            for denied in self.DENIED_DOMAINS:
                if denied in domain:
                    return domain, DomainTier.UNTRUSTED
            
            # Check each tier
            for tier1_domain in self.TIER_1_DOMAINS:
                if domain.endswith(tier1_domain) or tier1_domain in domain:
                    return domain, DomainTier.TIER_1_GOVERNMENT
            
            for tier2_domain in self.TIER_2_DOMAINS:
                if tier2_domain in domain:
                    return domain, DomainTier.TIER_2_INTERNATIONAL
            
            for tier3_domain in self.TIER_3_DOMAINS:
                if domain.endswith(tier3_domain) or tier3_domain in domain:
                    return domain, DomainTier.TIER_3_ACADEMIC
            
            for tier4_domain in self.TIER_4_DOMAINS:
                if tier4_domain in domain:
                    return domain, DomainTier.TIER_4_MAJOR_NEWS
            
            for tier5_domain in self.TIER_5_DOMAINS:
                if tier5_domain in domain:
                    return domain, DomainTier.TIER_5_VERIFIED
            
            # Unknown domain
            return domain, DomainTier.UNTRUSTED
            
        except Exception as e:
            logger.warning(f"Error parsing URL {url}: {e}")
            return url, DomainTier.UNTRUSTED
    
    def calculate_reliability(
        self, 
        url: str, 
        citation_count: int = 0,
        days_old: int = 0
    ) -> SourceReliabilityScore:
        """Calculate reliability score for a URL."""
        domain, tier = self.classify_domain(url)
        
        score = SourceReliabilityScore(
            url=url,
            domain=domain,
            tier=tier
        )
        
        # Citation boost (normalized, max 0.1)
        if citation_count > 0:
            score.citation_boost = min(0.1, citation_count * 0.01)
        
        # Recency boost (fresher = better, max 0.05)
        if days_old >= 0:
            if days_old < 30:
                score.recency_boost = 0.05
            elif days_old < 90:
                score.recency_boost = 0.03
            elif days_old < 365:
                score.recency_boost = 0.01
        
        score.calculate()
        return score
    
    def filter_search_results(
        self, 
        results: List[Dict[str, Any]],
        min_threshold: float = None,
        max_results: int = None
    ) -> List[FilteredSearchResult]:
        """
        Filter search results by reputation.
        
        Args:
            results: Raw search results with 'url', 'title', 'content' keys
            min_threshold: Minimum reliability score (default: MIN_RELIABILITY_THRESHOLD)
            max_results: Maximum results to return (default: MAX_TRUSTED_SOURCES)
        
        Returns:
            List of FilteredSearchResult that passed the reputation filter
        """
        min_threshold = min_threshold or self.MIN_RELIABILITY_THRESHOLD
        max_results = max_results or self.MAX_TRUSTED_SOURCES
        
        filtered = []
        
        for result in results:
            url = result.get("url", "")
            if not url:
                continue
            
            # Calculate reliability
            reliability = self.calculate_reliability(
                url,
                citation_count=result.get("citations", 0),
                days_old=result.get("days_old", 0)
            )
            
            # Apply threshold
            if reliability.final_score >= min_threshold:
                filtered.append(FilteredSearchResult(
                    url=url,
                    title=result.get("title", ""),
                    content=result.get("content", ""),
                    reliability_score=reliability,
                    metadata=result.get("metadata", {})
                ))
            else:
                logger.debug(
                    f"Filtered out {url} (score: {reliability.final_score:.2f} < {min_threshold})"
                )
        
        # Sort by reliability score (highest first)
        filtered.sort(key=lambda x: x.reliability_score.final_score, reverse=True)
        
        # Limit results
        return filtered[:max_results]
    
    def search(
        self, 
        query: str,
        search_provider: str = "tavily"
    ) -> List[FilteredSearchResult]:
        """
        Execute a search with reputational filtering.
        
        This is a placeholder that should be integrated with actual search providers
        like Tavily, Exa, or SerpAPI.
        """
        logger.info(f"[ReputationalSearch] Executing filtered search for: {query}")
        
        # Placeholder for actual search integration
        # In production, this would call the actual search API
        raw_results = self._execute_search(query, search_provider)
        
        # Apply reputational filter
        filtered = self.filter_search_results(raw_results)
        
        logger.info(
            f"[ReputationalSearch] Filtered {len(raw_results)} results down to {len(filtered)} trusted sources"
        )
        
        return filtered
    
    def _execute_search(
        self, 
        query: str, 
        provider: str
    ) -> List[Dict[str, Any]]:
        """
        Execute actual search (placeholder for integration).
        
        In production, integrate with:
        - Tavily API
        - Exa API
        - SerpAPI
        - Custom crawler
        """
        # Placeholder - return empty for now
        # Real implementation would call external search APIs
        return []
    
    def get_trusted_domains_summary(self) -> Dict[str, List[str]]:
        """Get summary of trusted domains by tier."""
        return {
            "tier_1_government": list(self.TIER_1_DOMAINS),
            "tier_2_international": list(self.TIER_2_DOMAINS),
            "tier_3_academic": list(self.TIER_3_DOMAINS),
            "tier_4_news": list(self.TIER_4_DOMAINS),
            "tier_5_verified": list(self.TIER_5_DOMAINS),
            "denied": list(self.DENIED_DOMAINS)
        }


# Singleton instance
reputational_search = ReputationalSearch()


# Export
__all__ = [
    "ReputationalSearch",
    "reputational_search",
    "FilteredSearchResult",
    "SourceReliabilityScore",
    "DomainTier"
]
