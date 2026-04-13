"""
Legal Signal Extractor package.

This module family converts legal text into structured micro-signals while
keeping source snippets attached for interpretive validation.
"""

from .signals import LEGAL_SIGNALS
from .segmenter import atomize_document, atomize_with_spans
from .extractor import (
    CitationSpan,
    LegalSignal,
    LegalSignalExtractor,
    PrecedenceEngine,
    legal_signal_extractor,
    precedence_engine,
)

__all__ = [
    "LEGAL_SIGNALS",
    "atomize_document",
    "atomize_with_spans",
    "CitationSpan",
    "LegalSignal",
    "LegalSignalExtractor",
    "PrecedenceEngine",
    "legal_signal_extractor",
    "precedence_engine",
]
