"""
Clause segmenter for legal documents.

Converts large legal paragraphs into smaller rule-sized atoms.
"""

from __future__ import annotations

import re
from typing import List, Tuple


SPLIT_PATTERN = re.compile(
    r";|(?=\(\w+\))|(?=\d+\.)|(?=Provided that)|(?=Provided further)|"
    r"(?=Subject to)|(?=Notwithstanding)|(?=Except)|(?=Unless)",
    re.IGNORECASE,
)


def atomize_document(raw_text: str) -> List[str]:
    """
    Break text into legal atoms.
    """
    if not raw_text:
        return []

    text = " ".join(raw_text.replace("\n", " ").split()).strip()
    if not text:
        return []

    parts = SPLIT_PATTERN.split(text)
    return [part.strip() for part in parts if part and len(part.strip()) > 10]


def atomize_with_spans(raw_text: str) -> List[Tuple[str, int, int]]:
    """
    Return (clause, start, end) tuples for citation tracing.
    """
    clauses = atomize_document(raw_text)
    text = " ".join(raw_text.replace("\n", " ").split()).strip()
    if not clauses:
        return []

    spans: List[Tuple[str, int, int]] = []
    cursor = 0
    for clause in clauses:
        idx = text.find(clause, cursor)
        if idx < 0:
            idx = text.find(clause)
        if idx < 0:
            idx = 0
        end = idx + len(clause)
        cursor = max(cursor, end)
        spans.append((clause, idx, end))
    return spans

