"""Legal modules — 4-Brain Legal Evidence Engine.

Brain 1 — Retriever:  rag_bridge (ChromaDB + metadata filtering)
Brain 2 — Filter:     signal_legal_mapper + legal_evidence_formatter
Brain 3 — Analyst:    legal_reasoner (LLM applicability analysis)
Brain 4 — Reasoner:   legal_output_validator (hallucination blocker)
"""

from Core.legal.legal_reasoner import LegalReasoner
from Core.legal.signal_legal_mapper import filter_legal_signals, get_legal_domains
from Core.legal.legal_evidence_formatter import format_legal_evidence, LegalEvidenceItem
from Core.legal.legal_output_validator import validate_legal_output
from Core.legal.legal_reasoner_prompt import build_user_prompt

__all__ = [
    "LegalReasoner",
    "filter_legal_signals",
    "get_legal_domains",
    "format_legal_evidence",
    "LegalEvidenceItem",
    "validate_legal_output",
    "build_user_prompt",
]
