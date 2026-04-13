"""
Intelligent Chunker — Section-Aware Document Splitting
=======================================================
Splits documents into chunks that preserve meaning by respecting
document structure instead of using arbitrary character counts.

Strategy by document type:
    Legal  → chunk by Article / Section / Clause
    Event  → chunk by paragraph groups (~512 tokens)
    Economic → keep tables and data blocks intact
    Generic → sliding window with overlap

Each chunk inherits all parent document metadata.
"""

import re
import math
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Approximate tokens per word (for English text)
_TOKENS_PER_WORD = 1.3


class IntelligentChunker:
    """
    Section-aware chunking that preserves document structure.

    Unlike naive chunking (split every N characters), this chunker:
    1. Respects document hierarchy (Articles, Sections, Paragraphs)
    2. Keeps related content together
    3. Adds overlap between chunks for retrieval continuity
    4. Attaches metadata to each chunk for provenance
    """

    def __init__(self, target_tokens: int = 512, overlap_tokens: int = 50):
        """
        Args:
            target_tokens:  Target chunk size in tokens.
            overlap_tokens: Overlap between chunks for context continuity.
        """
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.target_words = int(target_tokens / _TOKENS_PER_WORD)
        self.overlap_words = int(overlap_tokens / _TOKENS_PER_WORD)

    def chunk(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Split a normalized document into retrieval-ready chunks.

        Args:
            document: Normalized document dict (from DocumentNormalizer).

        Returns:
            List of chunk dicts, each with: id, text, metadata, chunk_index.
        """
        doc_type = document.get("metadata", {}).get("document_type", "unknown")
        knowledge_space = document.get("metadata", {}).get("knowledge_space", "event")
        sections = document.get("sections", [])
        text = document.get("text", "")

        # Route to appropriate strategy
        if knowledge_space == "legal" or doc_type in ("treaty", "law", "convention", "resolution"):
            raw_chunks = self._chunk_legal(sections, text)
        elif knowledge_space == "economic" or doc_type in ("trade_data", "sanction"):
            raw_chunks = self._chunk_economic(sections, text)
        else:
            raw_chunks = self._chunk_event(sections, text)

        # Attach metadata and IDs to each chunk
        doc_id = document.get("id", "unknown")
        doc_metadata = document.get("metadata", {})

        chunks = []
        for i, raw in enumerate(raw_chunks):
            chunk_id = f"{doc_id}_c{i:03d}"
            chunks.append({
                "id":          chunk_id,
                "text":        raw["text"],
                "heading":     raw.get("heading", ""),
                "chunk_index": i,
                "total_chunks": len(raw_chunks),
                "metadata": {
                    **doc_metadata,
                    "parent_doc_id": doc_id,
                    "parent_title":  document.get("title", ""),
                    "chunk_index":   i,
                    "chunk_heading": raw.get("heading", ""),
                },
            })

        if not chunks and text.strip():
            # Fallback: if no chunks produced, make at least one
            chunks.append({
                "id":          f"{doc_id}_c000",
                "text":        text[:self.target_words * 5],  # rough cap
                "heading":     document.get("title", ""),
                "chunk_index": 0,
                "total_chunks": 1,
                "metadata": {
                    **doc_metadata,
                    "parent_doc_id": doc_id,
                    "parent_title":  document.get("title", ""),
                    "chunk_index":   0,
                    "chunk_heading": document.get("title", ""),
                },
            })

        return chunks

    # ── Legal documents ──────────────────────────────────────────

    def _chunk_legal(
        self, sections: List[Dict], fallback_text: str
    ) -> List[Dict[str, str]]:
        """
        Chunk legal documents by structural sections.

        Each Article/Section becomes its own chunk.
        If a section is too large, split by clauses.
        If no sections detected, fall back to paragraph chunking.
        """
        if not sections:
            return self._chunk_by_paragraphs(fallback_text)

        chunks = []
        for section in sections:
            text = section.get("content", "").strip()
            heading = section.get("heading", "")

            if not text:
                continue

            word_count = len(text.split())

            if word_count <= self.target_words * 1.5:
                # Section fits in one chunk
                chunks.append({
                    "text":    f"{heading}\n\n{text}" if heading else text,
                    "heading": heading,
                })
            else:
                # Section too large — split by clauses/paragraphs
                sub_chunks = self._split_large_section(text, heading)
                chunks.extend(sub_chunks)

        return chunks if chunks else self._chunk_by_paragraphs(fallback_text)

    def _split_large_section(
        self, text: str, heading: str
    ) -> List[Dict[str, str]]:
        """Split an oversized section into sub-chunks."""
        # Try splitting by numbered clauses first
        clause_pattern = re.compile(r"\n(?=\d+\.\s)")
        parts = clause_pattern.split(text)

        if len(parts) <= 1:
            # No clauses — split by paragraphs
            return self._chunk_by_paragraphs(text, prefix_heading=heading)

        chunks = []
        buffer = []
        buffer_words = 0

        for part in parts:
            part = part.strip()
            if not part:
                continue

            part_words = len(part.split())

            if buffer_words + part_words > self.target_words and buffer:
                chunk_text = "\n".join(buffer)
                chunks.append({
                    "text":    f"{heading}\n\n{chunk_text}" if heading else chunk_text,
                    "heading": heading,
                })
                # Keep last part as overlap
                buffer = buffer[-1:] if buffer else []
                buffer_words = len(buffer[0].split()) if buffer else 0

            buffer.append(part)
            buffer_words += part_words

        # Flush remaining
        if buffer:
            chunk_text = "\n".join(buffer)
            chunks.append({
                "text":    f"{heading}\n\n{chunk_text}" if heading else chunk_text,
                "heading": heading,
            })

        return chunks

    # ── Event documents ──────────────────────────────────────────

    def _chunk_event(
        self, sections: List[Dict], fallback_text: str
    ) -> List[Dict[str, str]]:
        """
        Chunk news/event documents by paragraph groups.

        Groups paragraphs to hit ~target_tokens while keeping
        topic continuity.
        """
        # If sections exist, use them as starting points
        if sections:
            chunks = []
            for section in sections:
                text = section.get("content", "").strip()
                heading = section.get("heading", "")
                if text:
                    sub_chunks = self._chunk_by_paragraphs(text, prefix_heading=heading)
                    chunks.extend(sub_chunks)
            return chunks if chunks else self._chunk_by_paragraphs(fallback_text)

        return self._chunk_by_paragraphs(fallback_text)

    # ── Economic documents ───────────────────────────────────────

    def _chunk_economic(
        self, sections: List[Dict], fallback_text: str
    ) -> List[Dict[str, str]]:
        """
        Chunk economic/trade data documents.

        Tries to keep tables and data blocks intact.
        """
        # Similar to event chunking but with larger target for data tables
        if sections:
            chunks = []
            for section in sections:
                text = section.get("content", "").strip()
                heading = section.get("heading", "")
                if text:
                    # Use larger chunks for data-heavy content
                    sub_chunks = self._chunk_by_paragraphs(
                        text,
                        prefix_heading=heading,
                        target_override=self.target_words * 2,
                    )
                    chunks.extend(sub_chunks)
            return chunks if chunks else self._chunk_by_paragraphs(fallback_text)

        return self._chunk_by_paragraphs(fallback_text)

    # ── Generic paragraph chunking ───────────────────────────────

    def _chunk_by_paragraphs(
        self,
        text: str,
        prefix_heading: str = "",
        target_override: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """
        Split text into chunks by paragraph boundaries.

        Respects sentence boundaries within paragraphs.
        """
        if not text or not text.strip():
            return []

        target = target_override or self.target_words
        paragraphs = re.split(r"\n\s*\n", text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        if not paragraphs:
            return []

        chunks = []
        buffer = []
        buffer_words = 0

        for para in paragraphs:
            para_words = len(para.split())

            # If single paragraph exceeds target, split by sentences
            if para_words > target:
                # Flush buffer first
                if buffer:
                    chunk_text = "\n\n".join(buffer)
                    chunks.append({
                        "text":    f"{prefix_heading}\n\n{chunk_text}" if prefix_heading else chunk_text,
                        "heading": prefix_heading,
                    })
                    buffer = []
                    buffer_words = 0

                # Split long paragraph by sentences
                sentences = re.split(r'(?<=[.!?])\s+', para)
                sent_buffer = []
                sent_words = 0
                for sent in sentences:
                    sw = len(sent.split())
                    if sent_words + sw > target and sent_buffer:
                        chunk_text = " ".join(sent_buffer)
                        chunks.append({
                            "text":    f"{prefix_heading}\n\n{chunk_text}" if prefix_heading else chunk_text,
                            "heading": prefix_heading,
                        })
                        sent_buffer = []
                        sent_words = 0
                    sent_buffer.append(sent)
                    sent_words += sw
                if sent_buffer:
                    chunk_text = " ".join(sent_buffer)
                    chunks.append({
                        "text":    f"{prefix_heading}\n\n{chunk_text}" if prefix_heading else chunk_text,
                        "heading": prefix_heading,
                    })
                continue

            # Normal case: accumulate paragraphs
            if buffer_words + para_words > target and buffer:
                chunk_text = "\n\n".join(buffer)
                chunks.append({
                    "text":    f"{prefix_heading}\n\n{chunk_text}" if prefix_heading else chunk_text,
                    "heading": prefix_heading,
                })
                # Keep last paragraph as overlap
                if buffer:
                    overlap = buffer[-1]
                    buffer = [overlap]
                    buffer_words = len(overlap.split())
                else:
                    buffer = []
                    buffer_words = 0

            buffer.append(para)
            buffer_words += para_words

        # Flush remaining
        if buffer:
            chunk_text = "\n\n".join(buffer)
            chunks.append({
                "text":    f"{prefix_heading}\n\n{chunk_text}" if prefix_heading else chunk_text,
                "heading": prefix_heading,
            })

        return chunks


# ── Module-level convenience ─────────────────────────────────────

intelligent_chunker = IntelligentChunker()

__all__ = ["IntelligentChunker", "intelligent_chunker"]
