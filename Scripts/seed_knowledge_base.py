#!/usr/bin/env python3
"""
Knowledge Base Seeding Script
=============================
Seeds the IND-Diplomat knowledge base with authoritative diplomatic data.

Usage:
    python scripts/seed_knowledge_base.py --sources sovereign
    python scripts/seed_knowledge_base.py --sources all --priority 2
    python scripts/seed_knowledge_base.py --test-connectivity

Data Sources:
1. Indian Sovereign Registries (MEA, DGFT, Commerce)
2. Multilateral Trade APIs (WTO, UNCTAD, UN Comtrade)
3. Strategic Think Tanks (ICWA, ORF, RIS)
4. Legal Databases (UN Treaties, WTO Legal)
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import hashlib

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.crawler import (
    DiplomaticCrawler,
    INDIAN_SOVEREIGN_SOURCES,
    MULTILATERAL_API_SOURCES,
    THINK_TANK_SOURCES,
    LEGAL_DATABASE_SOURCES,
    ALL_SOURCES,
    SourceCategory
)
from external.trade_apis import (
    MultilateralAPIHub,
    WTOClient,
    UNCTADClient,
    ComtradeClient,
    WITSClient
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# TARGET URLs FOR SEEDING
# ============================================================

# Priority 1: Ground Truth Sources
GROUND_TRUTH_URLS = {
    "mea_treaties": [
        "https://mea.gov.in/treatylist-generic.htm",
        "https://mea.gov.in/bilateral-documents.htm?53/Bilateral/Multilateral_Documents",
    ],
    "mea_relations": [
        "https://mea.gov.in/foreign-relations.htm",
        # Specific country briefs (PDFs)
        "https://www.mea.gov.in/Portal/ForeignRelation/Brief_Jan_china_2023.pdf",
        "https://www.mea.gov.in/Portal/ForeignRelation/India-USA_Brief_2023.pdf",
        "https://www.mea.gov.in/Portal/ForeignRelation/Japan_Brief_2023.pdf",
        # Added for testing binary download
        "https://www.mea.gov.in/Portal/ForeignRelation/India-Australia_Brief_April_2023.pdf"
    ],
    "dgft": [
        "https://dgft.gov.in/CP/?opt=ft-policy",
        "https://dgft.gov.in/CP/?opt=notification",
        "https://dgft.gov.in/CP/?opt=public-notice",
    ],
    "commerce": [
        "https://commerce.gov.in/trade-statistics/",
        "https://commerce.gov.in/trade-statistics/export-import-data-bank/",
    ],
    "data_gov_in": [
        "https://data.gov.in/catalogs?sector=Commerce",
        "https://data.gov.in/apis",
    ]
}

# Priority 2: Legal Databases
LEGAL_URLS = {
    "un_treaties": [
        "https://treaties.un.org/Pages/ParticipationStatus.aspx",
        "https://treaties.un.org/Pages/LOTBrowse.aspx",
    ],
    "wto_legal": [
        "https://www.wto.org/english/docs_e/legal_e/legal_e.htm",
        "https://www.wto.org/english/tratop_e/dda_e/draft_text_gc_chair_e.htm",
    ],
    "un_conventions": [
        "https://www.un.org/depts/los/convention_agreements/convention_agreements.htm",
        "https://www.unodc.org/unodc/en/treaties/index.html",
    ]
}

# Priority 3: Think Tanks
THINK_TANK_URLS = {
    "icwa": [
        "https://icwa.in/show_list.php?type=publications",
        "https://icwa.in/show_list.php?type=viewpoints",
    ],
    "orf": [
        "https://www.orfonline.org/research",
        "https://www.orfonline.org/expert-speak",
    ],
    "ris": [
        "http://ris.org.in/policy-brief",
        "http://ris.org.in/discussion-paper",
    ],
    "dpg": [
        "https://www.delhipolicygroup.org/publications.php?type=policy-briefs",
    ]
}


class KnowledgeBaseSeeder:
    """
    Seeds the IND-Diplomat knowledge base with authoritative data.
    """
    
    def __init__(self, output_dir: str = "data/knowledge_base"):
        self.crawler = DiplomaticCrawler()
        self.api_hub = MultilateralAPIHub()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.stats = {
            "started_at": None,
            "completed_at": None,
            "sources_crawled": 0,
            "documents_ingested": 0,
            "api_calls_made": 0,
            "errors": []
        }

    async def _save_data(self, category: str, source: str, data: Any, binary_url: str = None):
        """
        Save data to structured directory.
        
        Args:
            category: Source category (sovereign, multilateral, etc.)
            source: Source name (mea, wto, etc.)
            data: JSON data or None if binary
            binary_url: URL to download if binary file
        """
        # Create directory: output_dir/category/source/
        save_dir = self.output_dir / category / source
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Binary download
        if binary_url:
            filename = os.path.basename(urlparse(binary_url).path)
            if not filename or filename == "/":
                filename = f"doc_{hashlib.sha256(binary_url.encode()).hexdigest()[:8]}.pdf"
            
            # Add date prefix if not present
            date_str = datetime.now().strftime('%Y-%m-%d')
            if not filename.startswith(date_str):
                filename = f"{date_str}_{filename}"
                
            file_path = save_dir / filename
            success = await self.crawler.download_file(binary_url, str(file_path))
            if success:
                logger.info(f"[{category.upper()}] Downloaded binary {filename} to {file_path}")
            else:
                logger.error(f"[{category.upper()}] Failed to download binary {binary_url}")
            return

        # JSON Save
        if data:
            filename = f"{datetime.now().strftime('%Y-%m-%d')}.json"
            file_path = save_dir / filename
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"[{category.upper()}] Saved {source} data to {file_path}")

    async def seed_sovereign_sources(self) -> Dict[str, Any]:
        """Seed Indian Sovereign Registry sources."""
        logger.info("=" * 60)
        logger.info("SEEDING INDIAN SOVEREIGN SOURCES (Ground Truth)")
        logger.info("=" * 60)
        
        results = {}
        
        async def crawl_and_process(key: str, urls: List[str]):
            source_results = []
            logger.info(f"[{key.upper()}] Processing index pages...")
            
            for url in urls:
                try:
                    # 1. Expand Index Page
                    logger.info(f"[{key.upper()}] Spidering index: {url}")
                    found_links = await self.crawler.extract_links(url, patterns=[r'\.pdf$', r'\.docx$'])
                    logger.info(f"[{key.upper()}] Found {len(found_links)} documents in {url}")
                    
                    # 2. Download all found documents
                    for doc_url in found_links:
                         try:
                             await self._save_data("sovereign", key, None, binary_url=doc_url)
                             self.stats["documents_ingested"] += 1
                         except Exception as e:
                             logger.error(f"Failed to download {doc_url}: {e}")

                    # 3. Also crawl the index page itself as metadata
                    result = await self.crawler.crawl_site(url)
                    source_results.append(result)
                    self.stats["documents_ingested"] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                    self.stats["errors"].append(f"{key}: {e}")
            
            if source_results:
                results[key] = source_results
                await self._save_data("sovereign", key, source_results)

        await crawl_and_process("mea", GROUND_TRUTH_URLS["mea_treaties"] + GROUND_TRUTH_URLS["mea_relations"])
        await crawl_and_process("dgft", GROUND_TRUTH_URLS["dgft"])
        await crawl_and_process("commerce", GROUND_TRUTH_URLS["commerce"])
        
        self.stats["sources_crawled"] += 3
        return results
    
    async def seed_multilateral_apis(self) -> Dict[str, Any]:
        """Seed Multilateral Trade API data."""
        logger.info("=" * 60)
        logger.info("SEEDING MULTILATERAL TRADE APIs (Live Signals)")
        logger.info("=" * 60)
        
        results = {}
        
        # WITS (Open)
        try:
            wits_data = await self.api_hub.wits.fetch_indicator("MPRT-TRD-VL", reporter="IND", year="2023")
            wits_json = [
                {
                    "indicator": d.indicator,
                    "value": d.value,
                    "year": d.year,
                    "partner": d.partner,
                    "source": d.source
                } 
                for d in wits_data
            ]
            results["wits"] = wits_json
            self._save_data("multilateral", "wits", wits_json)
            self.stats["api_calls_made"] += 1
        except Exception as e:
            self.stats["errors"].append(f"WITS API: {e}")

        # Others (Placeholder for authenticated)
        # In production, these would fetch real data if keys exist
        
        return results
    
    async def seed_legal_databases(self) -> Dict[str, Any]:
        """Seed Legal & Treaty databases."""
        logger.info("=" * 60)
        logger.info("SEEDING LEGAL DATABASES")
        logger.info("=" * 60)
        
        results = {}
        
        async def crawl_and_save(key: str, urls: List[str]):
            source_results = []
            logger.info(f"[Legal] Crawling {key}...")
            for url in urls:
                try:
                    result = await self.crawler.crawl_site(url)
                    source_results.append(result)
                    self.stats["documents_ingested"] += 1
                except Exception as e:
                    self.stats["errors"].append(f"Legal {key}: {e}")
            
            results[key] = source_results
            self._save_data("legal", key, source_results)

        for category, urls in LEGAL_URLS.items():
            await crawl_and_save(category, urls)
        
        self.stats["sources_crawled"] += len(LEGAL_URLS)
        return results
    
    async def seed_think_tanks(self) -> Dict[str, Any]:
        """Seed Strategic Think Tank sources."""
        logger.info("=" * 60)
        logger.info("SEEDING THINK TANK SOURCES (Context & Perspectives)")
        logger.info("=" * 60)
        
        results = {}
        
        for org, urls in THINK_TANK_URLS.items():
            logger.info(f"[Think Tank] Crawling {org.upper()}...")
            org_results = []
            
            for url in urls:
                try:
                    # Use stealth mode for think tanks
                    result = await self.crawler.crawl_site(url, stealth=True)
                    org_results.append(result)
                    self.stats["documents_ingested"] += 1
                except Exception as e:
                    self.stats["errors"].append(f"Think tank {org}: {e}")
            
            results[org] = org_results
            self._save_data("think_tanks", org, org_results)
        
        self.stats["sources_crawled"] += len(THINK_TANK_URLS)
        return results
    
    async def run_full_seed(self, max_priority: int = 2) -> Dict[str, Any]:
        """Run full knowledge base seeding workflow."""
        self.stats["started_at"] = datetime.utcnow().isoformat() + "Z"
        
        logger.info("=" * 60)
        logger.info("IND-DIPLOMAT KNOWLEDGE BASE SEEDING")
        logger.info(f"Target Directory: {self.output_dir}")
        logger.info("=" * 60)
        
        # Priority 1
        await self.seed_sovereign_sources()
        await self.seed_multilateral_apis()
        await self.seed_legal_databases()
        
        # Priority 2
        if max_priority >= 2:
            await self.seed_think_tanks()
        
        self.stats["completed_at"] = datetime.utcnow().isoformat() + "Z"
        
        # Save execution stats
        with open(self.output_dir / "seed_manifest.json", 'w') as f:
            json.dump(self.stats, f, indent=2)
            
        return {}  # Data already saved via _save_data

    async def test_connectivity(self) -> Dict[str, bool]:
        """Test connectivity to all configured sources."""
        logger.info("Testing connectivity to data sources...")
        results = {}
        # Test crawler sources
        for source in ALL_SOURCES[:5]: 
            try:
                result = await self.crawler.crawl_site(source.base_url)
                results[source.name] = result["status"] == 200
            except:
                results[source.name] = False
        return results


async def main():
    parser = argparse.ArgumentParser(description="Seed the IND-Diplomat knowledge base")
    parser.add_argument("--sources", choices=["sovereign", "apis", "legal", "think-tanks", "all"], default="all")
    parser.add_argument("--priority", type=int, choices=[1, 2, 3], default=2)
    parser.add_argument("--output", default="data/knowledge_base", help="Output directory for seeded data")
    parser.add_argument("--test-connectivity", action="store_true")
    
    args = parser.parse_args()
    
    seeder = KnowledgeBaseSeeder(output_dir=args.output)
    
    if args.test_connectivity:
        results = await seeder.test_connectivity()
        print("\nConnectivity Test Results:")
        for source, connected in results.items():
            status = "✓" if connected else "✗"
            print(f"  [{status}] {source}")
        return
    
    if args.sources == "all":
        await seeder.run_full_seed(max_priority=args.priority)
    elif args.sources == "sovereign":
        await seeder.seed_sovereign_sources()
    elif args.sources == "apis":
        await seeder.seed_multilateral_apis()
    elif args.sources == "legal":
        await seeder.seed_legal_databases()
    elif args.sources == "think-tanks":
        await seeder.seed_think_tanks()

if __name__ == "__main__":
    asyncio.run(main())
