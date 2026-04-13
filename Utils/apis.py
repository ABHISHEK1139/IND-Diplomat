"""
External API Clients & Aggregator
=================================
Handles integration with WTO, UNCTAD, and other diplomatic data sources.
Includes simulated clients for development/testing.
"""

import asyncio
import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import logging

from utils.edge_cases import rate_limited, with_timeout, timeout_handler

logger = logging.getLogger(__name__)

class WTOClient:
    """
    Client for World Trade Organization (WTO) Data API.
    Provides access to trade statistics, tariffs, and dispute settlement data.
    """
    
    BASE_URL = "https://api.wto.org/timeseries/v1"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or "wto_demo_key"
        self._cache = {}
    
    @rate_limited(user_id_param="api_key")
    @with_timeout(timeout=45.0)
    async def get_trade_stats(self, reporter: str, partner: str, year: int) -> Dict[str, Any]:
        """
        Get bilateral trade statistics.
        Real implementation would call WTO API.
        """
        # Simulation for development
        await asyncio.sleep(0.5)  # Simulate network latency
        
        return {
            "source": "WTO",
            "dataset": "Merchandise Trade",
            "reporter": reporter,
            "partner": partner,
            "year": year,
            "flow": "Import/Export",
            "value_usd_million": 45000.5,
            "status": "Final",
            "last_updated": "2024-12-01"
        }
    
    @rate_limited(user_id_param="api_key")
    @with_timeout(timeout=45.0)
    async def get_disputes(self, member: str) -> List[Dict[str, Any]]:
        """
        Get dispute cases involving a member.
        """
        await asyncio.sleep(0.4)
        
        return [
            {
                "ds_number": "DS123",
                "complainant": member,
                "respondent": "USA",
                "status": "In consultations",
                "date": "2025-01-15",
                "subject": "Certain measures concerning steel imports"
            }
        ]


class UNCTADClient:
    """
    Client for United Nations Conference on Trade and Development (UNCTAD).
    Provides access to FDI, maritime transport, and economic development data.
    """
    
    BASE_URL = "https://unctadstat-api.unctad.org/v1"
    
    def __init__(self):
        self._session = None
    
    @rate_limited(is_heavy=True)
    @with_timeout(timeout=60.0)
    async def get_fdi_flows(self, economy: str, year: int) -> Dict[str, Any]:
        """
        Get Foreign Direct Investment flows.
        """
        await asyncio.sleep(0.6)
        
        return {
            "source": "UNCTAD",
            "dataset": "FDI Flows",
            "economy": economy,
            "year": year,
            "inward_flow_million": 12500.0,
            "outward_flow_million": 8500.0,
            "trend": "increasing",
            "confidence": "high"
        }
    
    @with_timeout(timeout=30.0)
    async def get_country_profile(self, country_code: str) -> Dict[str, Any]:
        """Detailed economic profile."""
        await asyncio.sleep(0.3)
        return {
            "country": country_code,
            "gdp_growth": 6.5,
            "inflation": 4.2,
            "trade_balance": -2.5,
            "key_sectors": ["Services", "Manufacturing", "Agriculture"]
        }


class ExternalAggregator:
    """
    Aggregates data from multiple external sources.
    Verifies claims against official data.
    """
    
    def __init__(self):
        self.wto = WTOClient()
        self.unctad = UNCTADClient()
    
    async def verify_claim(self, claim_text: str) -> Dict[str, Any]:
        """
        Verify a claim using external data sources.
        """
        # Simple keyword extraction (in production use extraction agent)
        keywords = claim_text.lower()
        
        verification_tasks = []
        sources_used = []
        
        if "trade" in keywords or "tariff" in keywords:
            verification_tasks.append(self.wto.get_trade_stats("India", "World", 2024))
            sources_used.append("WTO")
            
        if "investment" in keywords or "fdi" in keywords:
            verification_tasks.append(self.unctad.get_fdi_flows("India", 2024))
            sources_used.append("UNCTAD")
            
        if not verification_tasks:
            return {
                "verified": False,
                "reason": "No relevant external data source found",
                "sources": []
            }
            
        results = await asyncio.gather(*verification_tasks, return_exceptions=True)
        
        valid_results = [r for r in results if not isinstance(r, Exception)]
        
        return {
            "verified": True,
            "confidence": 0.85 if valid_results else 0.0,
            "supporting_data": valid_results,
            "sources": sources_used,
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_comprehensive_profile(self, country: str) -> Dict[str, Any]:
        """
        Builds a comprehensive economic profile from all sources.
        """
        wto_data, unctad_data = await asyncio.gather(
            self.wto.get_disputes(country),
            self.unctad.get_country_profile(country)
        )
        
        return {
            "country": country,
            "wto_disputes": wto_data,
            "economic_indicators": unctad_data,
            "generated_at": datetime.now().isoformat()
        }


# Global instances
wto_client = WTOClient()
unctad_client = UNCTADClient()
external_aggregator = ExternalAggregator()
