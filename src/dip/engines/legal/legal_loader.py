"""
Legal Loader — Deprecated (Live Web Search)
=============================================

The legal module now uses live DuckDuckGo web search instead of
loading local PDF/HTML/DOCX treaty files from disk.

This file is kept as a minimal stub for backward compatibility.
The old OCR/PDF pipeline has been removed.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("Legal.loader")


class LegalLoader:
    """Stub for backward compatibility. No longer loads local files.

    The legal pipeline now uses DuckDuckGo live search via
    legal_indexer.py and treaty_rag_pipeline.py.
    """

    def __init__(self, **kwargs):
        self.documents = {}
        self.loaded = True
        logger.info(
            "LegalLoader is deprecated. Treaty data is now fetched "
            "via live DuckDuckGo web search."
        )

    def load(self):
        """No-op. Returns empty dict."""
        return self.documents
