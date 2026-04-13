"""
Signal deduplication helpers for Layer-2 extraction.
"""

from __future__ import annotations

import hashlib


def normalize(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def signal_signature(country: str, signal_type: str, sentence: str) -> str:
    base = f"{normalize(country)}:{normalize(signal_type)}:{normalize(sentence)}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


__all__ = ["normalize", "signal_signature"]

