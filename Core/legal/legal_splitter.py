"""
Core.legal.legal_splitter   —   Structure-Aware Legal Chunker
==============================================================

Legal documents are **hierarchical**: Treaty → Part → Chapter → Article
→ Clause → Sub-clause.  Naive token-window chunking destroys legal
meaning ("States shall not use force…" | "…except in self-defense").

This module splits by **legal structure**, not token count:

    1.  **Primary split** — regex detects Article / Section / Chapter /
        Part / Rule / Regulation headings (multilingual patterns).
    2.  **Preamble capture** — text before the first heading becomes its
        own chunk (preambles state treaty purpose & scope).
    3.  **Sub-article merge** — tiny fragments (<MIN_CHUNK) get merged
        with the previous article so context is preserved.
    4.  **Oversized split** — articles longer than MAX_CHUNK get broken
        at clause boundaries ((a), (b), 1., 2.) with overlap, never
        mid-sentence.
    5.  **Fallback** — for documents with no detected structure (raw OCR,
        trade data files), a sentence-boundary–aware windowed chunker.

Each chunk is returned as a ``LegalChunk`` with metadata:
    article_number, heading, domain hint, position_in_doc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── Configuration ─────────────────────────────────────────────────────
MIN_CHUNK = 120          # chars — merge fragments shorter than this
MAX_CHUNK = 3000         # chars — split articles longer than this
FALLBACK_CHUNK_SIZE = 1400
FALLBACK_OVERLAP = 200
FALLBACK_MIN = 250


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class LegalChunk:
    """One semantically coherent piece of law."""
    text: str
    heading: str = ""
    article_number: str = ""
    chunk_type: str = "article"       # article | preamble | annex | fallback
    position: int = 0                 # ordinal position in document
    parent_heading: str = ""          # Chapter / Part this article belongs to
    metadata: Dict[str, str] = field(default_factory=dict)


# ── Heading detection (the core regex) ────────────────────────────────

# Level-1 headings (Part, Title, Chapter) — used to track parent context
_PART_RE = re.compile(
    r"^(?:"
    r"(?:PART|Part|TITLE|Title)\s+[IVXLC\d]+\.?"
    r"|(?:CHAPTER|Chapter)\s+[IVXLC\d]+\.?"
    r")"
    r"[.\s\-\u2013\u2014:]*(.*)$",
    re.MULTILINE,
)

# Level-2 headings (Article, Section, Rule, etc.) — the primary split points
_ARTICLE_RE = re.compile(
    r"^[ \t]*(?:"
    r"(?:Article|ARTICLE|Art\.?)\s+(\d+[A-Za-z]*(?:bis|ter|quater)?)"   # Article 51, Art. 2(4)
    r"|(?:Section|SECTION|Sec\.?)\s+(\d+[A-Za-z]*)"                    # Section 3
    r"|(?:Rule|RULE)\s+(\d+[A-Za-z]*)"                                 # Rule 70
    r"|(?:Regulation|REGULATION)\s+(\d+[A-Za-z]*)"                     # Regulation 5
    r"|(?:Clause|CLAUSE)\s+(\d+[A-Za-z]*)"                             # Clause 12
    r"|(?:Schedule|SCHEDULE)\s+([IVXLC\d]+)"                           # Schedule II
    r"|(?:Annex|ANNEX|Appendix|APPENDIX)\s+([IVXLC\d]+[A-Za-z]*)"     # Annex III
    r")"
    r"[.\s\-\u2013\u2014:]*(.*)$",
    re.MULTILINE,
)

# Sub-clause boundaries for splitting oversized articles
_CLAUSE_BOUNDARY_RE = re.compile(
    r"(?:^|\n)[ \t]*(?:"
    r"\d+\.\s"                    # 1. 2. 3.
    r"|[a-z]\)\s"                 # a) b) c)
    r"|\([a-z]\)\s"              # (a) (b) (c)
    r"|\([ivxlc]+\)\s"           # (i) (ii) (iii)
    r"|\([A-Z]\)\s"              # (A) (B) (C)
    r")",
    re.IGNORECASE,
)


# ── Text cleaning ────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Aggressive cleaning for legal HTML / OCR noise."""
    if not text:
        return ""

    # Remove Constitute Project JS template tags
    text = re.sub(r"\[\[.*?\]\]", "", text)

    # Remove HTML leftovers
    text = re.sub(r"<[^>]+>", " ", text)

    # Remove CSS / JS blocks that leaked through
    text = re.sub(r"\{[^}]{10,}\}", " ", text)

    # Normalize whitespace (preserve paragraph breaks)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Fix OCR hyphenation
    text = re.sub(r"(\w)- (\w)", r"\1\2", text)

    # Normalize quotes
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", " - ")

    return text.strip()


# Legacy alias
def normalize_text(text: str) -> str:
    return _clean_text(text)


# ── Metadata extraction from filenames ────────────────────────────────

_YEAR_RE = re.compile(r"(1[89]\d{2}|20[0-2]\d)")

_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "maritime":     ["unclos", "maritime", "sea", "ocean", "naval", "eez", "territorial_waters"],
    "war":          ["geneva", "armed_conflict", "war", "humanitarian", "hague", "weapons"],
    "trade":        ["wto", "gatt", "trade", "tariff", "marrakesh", "trips", "imf"],
    "sanctions":    ["sanction", "restrictive", "ofac", "embargo"],
    "human_rights": ["human_rights", "cedaw", "crc", "udhr", "icescr", "torture", "cat"],
    "nuclear":      ["nuclear", "npt", "nonproliferation", "iaea", "ctbt"],
    "constitution": ["constitution"],
    "diplomatic":   ["vienna", "diplomatic", "consular", "diplomatic_relations"],
    "cyber":        ["cyber", "tallinn", "information_security"],
    "environment":  ["environment", "climate", "biodiversity", "paris_agreement"],
    "defense":      ["defense", "defence", "nato", "collective", "alliance", "military"],
    "border":       ["border", "boundary", "territorial", "shimla", "tashkent"],
    "investment":   ["investment", "bit", "bilateral_investment"],
    "tax":          ["tax", "dtaa", "double_taxation", "fiscal"],
    "organization": ["charter", "constitutive", "founding", "asean", "bimstec", "sco", "saarc"],
}


def _infer_domain(filepath: str, root: str) -> str:
    """Infer the legal domain from filepath and root directory name."""
    path_lower = filepath.replace("\\", "/").lower()

    for domain, keywords in _DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in path_lower:
                return domain

    root_map = {
        "global": "international",
        "trade": "trade",
        "constitutions_text": "constitution",
        "india_stack": "defense",
        "india_active_treaties": "bilateral",
        "international": "human_rights",
        "organizations": "organization",
        "countries": "domestic",
    }
    return root_map.get(root, "general")


def _infer_treaty_name(filepath: str) -> str:
    """Extract a human-readable treaty name from the filename."""
    from pathlib import Path
    stem = Path(filepath).stem

    # Remove numeric IDs (like 108620000000000495)
    if stem.isdigit() or (len(stem) > 12 and stem.replace("_", "").isdigit()):
        return ""

    name = stem.replace("_", " ").replace("-", " ").strip()
    name = re.sub(r"\s+", " ", name)
    return name.title()


def _infer_year(filepath: str) -> str:
    """Extract the most likely year from filename."""
    match = _YEAR_RE.search(filepath)
    return match.group(1) if match else ""


def _infer_country(filepath: str, root: str) -> str:
    """Extract country from filename if present."""
    from pathlib import Path
    stem = Path(filepath).stem

    if root == "constitutions_text":
        parts = stem.split("_")
        if len(parts) >= 2 and _YEAR_RE.match(parts[-1]):
            return " ".join(parts[:-1])

    return ""


# ── Core splitting logic ─────────────────────────────────────────────

def _split_at_headings(text: str) -> List[Tuple[str, str, str]]:
    """
    Split text at Article/Section headings.

    Returns list of (article_number, heading_text, body_text).
    The first element may be a preamble (article_number="PREAMBLE").
    """
    matches = list(_ARTICLE_RE.finditer(text))

    if not matches:
        return []

    results: List[Tuple[str, str, str]] = []

    # Preamble: everything before the first heading
    preamble = text[:matches[0].start()].strip()
    if len(preamble) > MIN_CHUNK:
        results.append(("PREAMBLE", "Preamble", preamble))

    for i, m in enumerate(matches):
        # Article number is in whichever capture group matched
        art_num = ""
        for g in m.groups()[:-1]:  # last group is the heading text
            if g:
                art_num = g.strip()
                break

        heading_text = m.group().strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end].strip()

        full = f"{heading_text}\n{body}".strip() if body else heading_text
        results.append((art_num, heading_text, full))

    return results


def _split_oversized(text: str, heading: str = "") -> List[str]:
    """Split an oversized article at clause boundaries."""
    boundaries = [m.start() for m in _CLAUSE_BOUNDARY_RE.finditer(text)]

    if not boundaries or len(boundaries) < 2:
        return _sentence_split(text, heading)

    chunks: List[str] = []
    prefix = f"{heading}\n" if heading else ""

    for i in range(len(boundaries)):
        start = boundaries[i]
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(text)
        segment = text[start:end].strip()

        if not segment:
            continue

        if chunks and len(chunks[-1]) + len(segment) < MAX_CHUNK:
            chunks[-1] = chunks[-1] + "\n" + segment
        else:
            chunks.append(prefix + segment if prefix and not chunks else segment)

    merged: List[str] = []
    for c in chunks:
        if merged and len(c) < MIN_CHUNK:
            merged[-1] = merged[-1] + "\n" + c
        else:
            merged.append(c)

    return merged if merged else [text]


def _sentence_split(text: str, heading: str = "") -> List[str]:
    """Last-resort: split at sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: List[str] = []
    current = heading + "\n" if heading else ""

    for sent in sentences:
        if len(current) + len(sent) > MAX_CHUNK and len(current) > MIN_CHUNK:
            chunks.append(current.strip())
            current = (heading + "\n" if heading else "") + sent
        else:
            current += " " + sent

    if current.strip():
        chunks.append(current.strip())

    return chunks


# ── Fallback chunker (no legal structure detected) ────────────────────

def _fallback_chunks_structured(text: str) -> List[LegalChunk]:
    """Sentence-boundary-aware fallback for documents with no articles."""
    if len(text) <= FALLBACK_MIN:
        return [LegalChunk(text=text, chunk_type="fallback")] if text.strip() else []

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: List[LegalChunk] = []
    current = ""
    pos = 0

    for sent in sentences:
        if len(current) + len(sent) > FALLBACK_CHUNK_SIZE and len(current) >= FALLBACK_MIN:
            chunks.append(LegalChunk(
                text=current.strip(),
                chunk_type="fallback",
                position=pos,
            ))
            pos += 1
            current = sent
        else:
            current = (current + " " + sent).strip()

    if current.strip() and len(current.strip()) >= FALLBACK_MIN // 2:
        chunks.append(LegalChunk(
            text=current.strip(),
            chunk_type="fallback",
            position=pos,
        ))

    return chunks


# Legacy fallback (plain string list)
def _fallback_chunks(
    text: str, chunk_size: int = 1400, overlap: int = 200, min_len: int = 300
) -> List[str]:
    return [c.text for c in _fallback_chunks_structured(text) if c.text.strip()]


# ── Parent heading tracker ────────────────────────────────────────────

def _find_parent_headings(text: str) -> Dict[int, str]:
    """Map character positions to the most recent Part/Chapter heading."""
    parents: Dict[int, str] = {}
    for m in _PART_RE.finditer(text):
        parents[m.start()] = m.group().strip()
    return parents


def _get_parent_at(position: int, parent_map: Dict[int, str]) -> str:
    """Get the parent heading active at a given character position."""
    best = ""
    for pos, heading in sorted(parent_map.items()):
        if pos <= position:
            best = heading
        else:
            break
    return best


# ── Public API ────────────────────────────────────────────────────────

def split_legal_document(
    text: str,
    source_path: str = "",
    root: str = "",
) -> List[LegalChunk]:
    """
    Structure-aware legal document splitter.

    Returns a list of LegalChunk objects, each representing a
    semantically complete piece of law with metadata.
    """
    cleaned = _clean_text(text)
    if not cleaned or len(cleaned) < 80:
        return []

    # Infer metadata from filepath
    treaty_name = _infer_treaty_name(source_path)
    year = _infer_year(source_path)
    domain = _infer_domain(source_path, root)
    country = _infer_country(source_path, root)

    base_meta = {
        "treaty_name": treaty_name,
        "year": year,
        "domain": domain,
        "country": country,
    }

    parent_map = _find_parent_headings(cleaned)

    # Primary: split at legal headings
    sections = _split_at_headings(cleaned)

    if sections:
        chunks: List[LegalChunk] = []
        pos = 0

        for art_num, heading, body in sections:
            art_pos = cleaned.find(heading[:40]) if heading else 0
            parent = _get_parent_at(art_pos, parent_map) if parent_map else ""

            if len(body) > MAX_CHUNK:
                sub_texts = _split_oversized(body, heading)
                for j, sub in enumerate(sub_texts):
                    if len(sub.strip()) < MIN_CHUNK // 2:
                        continue
                    meta = dict(base_meta)
                    meta["article_number"] = art_num
                    meta["sub_chunk"] = str(j)
                    chunks.append(LegalChunk(
                        text=sub.strip(),
                        heading=heading,
                        article_number=art_num,
                        chunk_type="preamble" if art_num == "PREAMBLE" else "article",
                        position=pos,
                        parent_heading=parent,
                        metadata=meta,
                    ))
                    pos += 1
            else:
                if len(body.strip()) < MIN_CHUNK // 2:
                    if chunks:
                        chunks[-1].text += "\n" + body.strip()
                        continue
                    continue

                meta = dict(base_meta)
                meta["article_number"] = art_num
                chunks.append(LegalChunk(
                    text=body.strip(),
                    heading=heading,
                    article_number=art_num,
                    chunk_type="preamble" if art_num == "PREAMBLE" else "article",
                    position=pos,
                    parent_heading=parent,
                    metadata=meta,
                ))
                pos += 1

        if chunks:
            return chunks

    fb = _fallback_chunks_structured(cleaned)
    for chunk in fb:
        chunk.metadata = dict(base_meta)
    return fb


# ── Backwards-compatible wrapper ──────────────────────────────────────

def split_legal_text(text: str) -> List[str]:
    """
    Legacy API: returns list of text strings (no metadata).
    """
    chunks = split_legal_document(text)
    return [c.text for c in chunks if c.text.strip()]
