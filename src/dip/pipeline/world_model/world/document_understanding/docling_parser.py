import logging
import os
from typing import List

try:
    from docling.document_converter import DocumentConverter
except ImportError:
    DocumentConverter = None

logger = logging.getLogger("Layer3.DoclingParser")


class DoclingParser:
    """
    Wraps IBM's docling library to parse PDFs, Word docs, and complex reports
    into clean Markdown/structured text for downstream entity extraction.
    """

    def __init__(self):
        self.converter = None
        if DocumentConverter:
            self.converter = DocumentConverter()
        else:
            logger.warning("docling not installed. DoclingParser will fallback to simple text reading.")

    def parse_document(self, file_path: str) -> str:
        """
        Parses a complex document into Markdown text.
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return ""

        if not self.converter:
            # Fallback for when OSS isn't installed during dev/testing
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Fallback read failed: {e}")
                return ""

        logger.info(f"Using Docling to parse: {file_path}")
        try:
            result = self.converter.convert(file_path)
            # Export to markdown for the extractors
            return result.document.export_to_markdown()
        except Exception as e:
            logger.error(f"Docling parsing failed: {e}")
            return ""
