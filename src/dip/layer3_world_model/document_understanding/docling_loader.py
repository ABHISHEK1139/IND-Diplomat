"""
Docling Loader
================
Uses IBM's Docling to robustly parse PDFs, Word docs, and HTML
into clean, structured Document representations for the World Model.
"""

import logging
from typing import Optional

try:
    from docling.document_converter import DocumentConverter
except ImportError:
    DocumentConverter = None

logger = logging.getLogger("Layer3.DoclingLoader")


class DoclingLoader:
    """
    Wrapper around IBM Docling for deep document understanding.
    """
    
    def __init__(self):
        self._converter = None

    def _load_converter(self):
        if not DocumentConverter:
            logger.warning("Docling not installed. Falling back to simple text conversion.")
            return

        if self._converter is None:
            logger.info("Initializing Docling DocumentConverter")
            try:
                self._converter = DocumentConverter()
            except Exception as e:
                logger.error(f"Failed to load Docling: {e}")
                self._converter = None

    def parse(self, file_path_or_url: str) -> Optional[str]:
        """
        Parses a document into markdown.
        """
        self._load_converter()
        
        if self._converter is None:
            return None
            
        try:
            logger.info(f"Parsing document with Docling: {file_path_or_url}")
            result = self._converter.convert(file_path_or_url)
            # Return markdown representation
            return result.document.export_to_markdown()
        except Exception as e:
            logger.error(f"Docling parsing failed for {file_path_or_url}: {e}")
            return None
