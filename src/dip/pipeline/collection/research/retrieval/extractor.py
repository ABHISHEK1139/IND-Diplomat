"""
Politiq AI — Content Extractor
==============================

Uses trafilatura to extract clean text and metadata from raw HTML.
"""

import logging
from typing import Optional, Dict, Any
import trafilatura

from dip.pipeline.collection.research.schemas import Document

logger = logging.getLogger("Research.Extractor")


class ContentExtractor:
    """Extracts clean article text from raw HTML using trafilatura."""
    
    def extract(self, url: str, html: str, base_title: str = "") -> Optional[Document]:
        """
        Extract clean text and metadata from HTML.
        
        Args:
            url: The source URL
            html: Raw HTML string
            base_title: Fallback title if extraction fails to find one
            
        Returns:
            Document object or None if extraction fails.
        """
        if not html:
            return None
            
        try:
            # Trafilatura extracts text, removing nav, footer, ads, etc.
            result = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=True,
                include_links=False,
                output_format="json",
                with_metadata=True
            )
            
            if not result:
                logger.debug(f"Trafilatura returned empty for {url}")
                return None
                
            import json
            data = json.loads(result)
            
            clean_text = data.get("raw_text") or data.get("text", "")
            if not clean_text or len(clean_text) < 50:
                logger.debug(f"Extracted text too short for {url}")
                return None
                
            title = data.get("title") or base_title
            language = data.get("source-hostname")  # trafilatura doesn't always give lang directly in json out
            # Actually, trafilatura json often includes 'hostname', 'date', 'author'
            metadata = {
                "author": data.get("author"),
                "date": data.get("date"),
                "hostname": data.get("hostname"),
                "categories": data.get("categories"),
                "tags": data.get("tags")
            }
            
            return Document(
                title=title,
                url=url,
                html=html,
                clean_text=clean_text,
                language=language,
                metadata={k: v for k, v in metadata.items() if v}
            )
            
        except Exception as e:
            logger.error(f"Extraction failed for {url}: {e}")
            return None
