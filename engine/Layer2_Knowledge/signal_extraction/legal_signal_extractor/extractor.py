"""
Legal signal extractor core.

Hybrid rule-based parser:
- Segment legal text into clauses.
- Detect power-word signals.
- Attach original snippets for validation.
- Resolve precedence for downstream reasoning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import re

from pydantic import ValidationError

from schemas.legal_signal_schema import LegalSignalRecord
from engine.Layer2_Knowledge.legal_signal_dictionary import (
    detect_legal_signal_hits as detect_geopolitical_signal_hits,
)
from engine.Layer2_Knowledge.signal_deduplicator import signal_signature

from .segmenter import atomize_with_spans
from .signals import (
    LEGAL_SIGNALS,
    INTERPRETIVE_TERMS,
    CONDITIONAL_KEYWORDS,
    EXCEPTION_KEYWORDS,
    OVERRIDE_KEYWORDS,
    REFERENCE_PATTERN,
    choose_primary_signal,
    detect_signal_hits,
)


@dataclass
class CitationSpan:
    source: str
    span: str
    text: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LegalSignal:
    provision_id: str
    provision_type: str
    actor: str
    modality: str
    strength: float
    signal_type: str = "NONE"
    conditions: List[str] = field(default_factory=list)
    exceptions: List[str] = field(default_factory=list)
    overrides: List[Dict[str, str]] = field(default_factory=list)
    cross_refs: List[str] = field(default_factory=list)
    interpretive_terms: List[str] = field(default_factory=list)
    jurisdiction_level: str = "statute"
    temporal_validity: Dict[str, Optional[str]] = field(
        default_factory=lambda: {"from": None, "to": None}
    )
    burden_standard: Dict[str, str] = field(
        default_factory=lambda: {"burden_on": "unknown", "standard": "unknown"}
    )
    remedy_hint: str = "unknown"
    original_text: str = ""
    review_required: bool = False
    citations: List[CitationSpan] = field(default_factory=list)
    signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["citations"] = [item.to_dict() for item in self.citations]
        return payload


class LegalSignalExtractor:
    """Extract legal micro-signals from text/documents."""

    def extract_from_documents(self, documents: List[Dict[str, Any]]) -> List[LegalSignal]:
        signals: List[LegalSignal] = []
        for doc in documents:
            content = self._document_text(doc)
            if not content.strip():
                continue
            source = str(doc.get("id") or doc.get("metadata", {}).get("source") or "unknown")
            jurisdiction = self._jurisdiction_from_doc(doc)
            extracted = self.extract_from_text(
                text=content,
                source=source,
                jurisdiction_level=jurisdiction,
            )
            signals.extend(extracted)
            phrase_signals = self._extract_geopolitical_phrase_signals(
                text=content,
                source=source,
                jurisdiction_level=jurisdiction,
                actor_hint=self._actor_from_doc(doc),
            )
            signals.extend(phrase_signals)
        return signals

    def extract_from_text(
        self,
        text: str,
        source: str,
        jurisdiction_level: str = "statute",
    ) -> List[LegalSignal]:
        clauses_with_spans = atomize_with_spans(text)
        extracted: List[LegalSignal] = []

        for idx, (clause_text, start, end) in enumerate(clauses_with_spans, start=1):
            hits = detect_signal_hits(clause_text)
            signal_type = choose_primary_signal(hits)
            signal_meta = LEGAL_SIGNALS.get(signal_type, {})
            strength = self._compute_strength(hits)
            review_required = len(hits) == 0

            citation = CitationSpan(
                source=source,
                span=f"{start}:{end}",
                text=clause_text[:220],
            )
            signal = LegalSignal(
                provision_id=f"{source}:clause:{idx}",
                provision_type=self._provision_type(signal_type, clause_text),
                actor=self._detect_actor(clause_text),
                modality=self._modality(signal_type, signal_meta),
                strength=strength,
                signal_type=signal_type,
                conditions=self._extract_conditions(clause_text),
                exceptions=self._extract_exceptions(clause_text),
                overrides=self._extract_overrides(clause_text),
                cross_refs=self._extract_cross_refs(clause_text),
                interpretive_terms=self._extract_interpretive_terms(clause_text),
                jurisdiction_level=jurisdiction_level,
                temporal_validity=self._extract_temporal_validity(clause_text),
                burden_standard=self._extract_burden_standard(clause_text),
                remedy_hint=self._extract_remedy_hint(clause_text),
                original_text=clause_text,
                review_required=review_required,
                citations=[citation],
                signature=signal_signature(
                    country=self._detect_actor(clause_text),
                    signal_type=signal_type,
                    sentence=clause_text,
                ),
            )
            # Enforce structured signal contract before handing off to Layer-3.
            try:
                LegalSignalRecord.model_validate(signal.to_dict())
            except ValidationError:
                continue
            extracted.append(signal)

        return extracted

    def _extract_geopolitical_phrase_signals(
        self,
        text: str,
        source: str,
        jurisdiction_level: str,
        actor_hint: str = "",
    ) -> List[LegalSignal]:
        hits = detect_geopolitical_signal_hits(text)
        signals: List[LegalSignal] = []
        for idx, hit in enumerate(hits, start=1):
            phrase = str(hit.get("phrase") or "").strip()
            signal_type = str(hit.get("signal_type") or "NONE").strip() or "NONE"
            start = int(hit.get("start") or 0)
            end = int(hit.get("end") or start)
            snippet = self._snippet_with_phrase(text, start, end, phrase)
            citation = CitationSpan(
                source=source,
                span=f"{start}:{end}",
                text=snippet[:220],
            )
            signal = LegalSignal(
                provision_id=f"{source}:phrase:{idx}",
                provision_type=self._provision_type_from_phrase_signal(signal_type),
                actor=actor_hint or "unknown",
                modality="may",
                strength=max(0.1, min(1.0, float(hit.get("strength", 0.5)))),
                signal_type=signal_type,
                conditions=[],
                exceptions=[],
                overrides=[],
                cross_refs=[],
                interpretive_terms=[phrase] if phrase else [],
                jurisdiction_level=jurisdiction_level,
                temporal_validity={"from": None, "to": None},
                burden_standard={"burden_on": "unknown", "standard": "unknown"},
                remedy_hint="unknown",
                original_text=snippet,
                review_required=bool(hit.get("inferred", False)),
                citations=[citation],
                signature=signal_signature(
                    country=actor_hint or "unknown",
                    signal_type=signal_type,
                    sentence=snippet,
                ),
            )
            try:
                LegalSignalRecord.model_validate(signal.to_dict())
            except ValidationError:
                continue
            signals.append(signal)
        return signals

    def _compute_strength(self, hits: List[Dict[str, Any]]) -> float:
        if not hits:
            return 0.3
        magnitude = sum(abs(float(hit.get("weight", 0.5))) for hit in hits) / len(hits)
        return max(0.1, min(1.0, magnitude / 2.0))

    def _provision_type(self, signal_type: str, clause_text: str) -> str:
        if signal_type in LEGAL_SIGNALS:
            return str(LEGAL_SIGNALS[signal_type].get("provision_type", "duty"))
        lower = clause_text.lower()
        if "right" in lower:
            return "right"
        if "procedure" in lower:
            return "procedure"
        return "duty"

    def _modality(self, signal_type: str, signal_meta: Dict[str, Any]) -> str:
        if signal_type in LEGAL_SIGNALS:
            return str(signal_meta.get("modality", "may"))
        return "may"

    def _provision_type_from_phrase_signal(self, signal_type: str) -> str:
        lower = signal_type.lower()
        if "justification" in lower:
            return "exception"
        if "claim" in lower or "territorial" in lower:
            return "claim"
        if "warning" in lower or "pressure" in lower:
            return "assertion"
        if "accusation" in lower:
            return "accusation"
        if "alliance" in lower:
            return "commitment"
        return "duty"

    def _snippet_with_phrase(self, text: str, start: int, end: int, canonical_phrase: str) -> str:
        lo = max(0, start - 80)
        hi = min(len(text), max(end + 80, lo + 1))
        snippet = " ".join(text[lo:hi].split()).strip()
        if not snippet:
            snippet = canonical_phrase or text[:120]
        if canonical_phrase and canonical_phrase.lower() not in snippet.lower():
            return f"{canonical_phrase}: {snippet}".strip()
        return snippet

    def _document_text(self, doc: Dict[str, Any]) -> str:
        content = str(doc.get("content", "") or "").strip()
        if content:
            return content
        text = str(doc.get("text", "") or "").strip()
        if text:
            return text
        title = str(doc.get("title", "") or "").strip()
        summary = str(doc.get("summary", "") or "").strip()
        merged = " ".join(part for part in (title, summary) if part)
        return merged.strip()

    def _actor_from_doc(self, doc: Dict[str, Any]) -> str:
        metadata = doc.get("metadata", {}) or {}
        actors = metadata.get("actors")
        if isinstance(actors, list):
            for actor in actors:
                text = str(actor or "").strip()
                if text:
                    return text
        if isinstance(actors, str):
            for part in actors.split(","):
                text = str(part or "").strip()
                if text:
                    return text
        for key in ("actor", "country", "state"):
            value = metadata.get(key)
            if value:
                return str(value).strip()
        return "unknown"

    def _detect_actor(self, clause_text: str) -> str:
        lower = clause_text.lower()
        if "court" in lower:
            return "court"
        if "state" in lower or "government" in lower:
            return "state"
        if "authority" in lower or "commission" in lower:
            return "authority"
        if "citizen" in lower or "person" in lower:
            return "person"
        return "unknown"

    def _extract_conditions(self, clause_text: str) -> List[str]:
        lower = clause_text.lower()
        found = [word for word in CONDITIONAL_KEYWORDS if word in lower]
        return sorted(set(found))

    def _extract_exceptions(self, clause_text: str) -> List[str]:
        lower = clause_text.lower()
        found = [word for word in EXCEPTION_KEYWORDS if word in lower]
        return sorted(set(found))

    def _extract_overrides(self, clause_text: str) -> List[Dict[str, str]]:
        overrides: List[Dict[str, str]] = []
        for keyword in OVERRIDE_KEYWORDS:
            pattern = r"\b" + re.escape(keyword) + r"\s+([^.;]+)"
            for match in re.finditer(pattern, clause_text, flags=re.IGNORECASE):
                overrides.append({"type": keyword, "target": match.group(1).strip()})
        return overrides

    def _extract_cross_refs(self, clause_text: str) -> List[str]:
        refs = [m.group(0).strip() for m in REFERENCE_PATTERN.finditer(clause_text)]
        return list(dict.fromkeys(refs))

    def _extract_interpretive_terms(self, clause_text: str) -> List[str]:
        lower = clause_text.lower()
        terms = [term for term in INTERPRETIVE_TERMS if term in lower]
        return sorted(terms)

    def _extract_temporal_validity(self, clause_text: str) -> Dict[str, Optional[str]]:
        start = None
        end = None

        start_match = re.search(r"\b((?:19|20)\d{2})\b", clause_text)
        if start_match:
            start = f"{start_match.group(1)}-01-01"

        end_match = re.search(r"\buntil\s+([A-Za-z0-9 ,/-]+)", clause_text, flags=re.IGNORECASE)
        if end_match:
            end = end_match.group(1).strip()

        return {"from": start, "to": end}

    def _extract_burden_standard(self, clause_text: str) -> Dict[str, str]:
        lower = clause_text.lower()
        burden_on = "unknown"
        standard = "unknown"
        if "state shall prove" in lower or "government shall prove" in lower:
            burden_on = "state"
        elif "petitioner shall prove" in lower or "applicant shall prove" in lower:
            burden_on = "petitioner"

        if "strict scrutiny" in lower or "strictly" in lower:
            standard = "strict"
        elif "preponderance" in lower:
            standard = "preponderance"
        elif "reasonable" in lower or "proportionate" in lower:
            standard = "reasonableness"

        return {"burden_on": burden_on, "standard": standard}

    def _extract_remedy_hint(self, clause_text: str) -> str:
        lower = clause_text.lower()
        if "void" in lower or "invalid" in lower:
            return "void"
        if "read down" in lower:
            return "read_down"
        if "injunction" in lower:
            return "injunction"
        if "damages" in lower or "compensation" in lower:
            return "damages"
        return "unknown"

    def _jurisdiction_from_doc(self, doc: Dict[str, Any]) -> str:
        metadata = doc.get("metadata", {}) or {}
        for key in ("jurisdiction_level", "authority_level", "level"):
            value = metadata.get(key)
            if value:
                return str(value).lower()

        doc_type = str(metadata.get("type", "")).lower()
        if "constitution" in doc_type:
            return "constitution"
        if "rule" in doc_type or "regulation" in doc_type:
            return "rule"
        if "case" in doc_type:
            return "case"
        if "treaty" in doc_type:
            return "treaty"
        return "statute"


class PrecedenceEngine:
    """Resolve conflict ordering among legal signals."""

    JURISDICTION_WEIGHT = {
        "constitution": 100,
        "treaty": 90,
        "statute": 80,
        "rule": 70,
        "regulation": 65,
        "case": 60,
        "unknown": 50,
    }

    MODALITY_WEIGHT = {
        "must": 30,
        "shall": 26,
        "prohibited": 29,
        "may": 16,
    }

    SIGNAL_TYPE_WEIGHT = {
        "PROHIBITION": 14,
        "OBLIGATION": 12,
        "PERMISSION": 8,
        "JUSTIFICATION": 10,
        "LOOPHOLE": 7,
        "NONE": 5,
    }

    def rank(self, signals: List[LegalSignal]) -> List[LegalSignal]:
        return sorted(signals, key=self._score, reverse=True)

    def resolve_conflicts(self, signals: List[LegalSignal]) -> Dict[str, Any]:
        ranked = self.rank(signals)
        groups: Dict[Tuple[str, str], List[LegalSignal]] = {}
        for signal in ranked:
            key = (signal.actor, signal.provision_type)
            groups.setdefault(key, []).append(signal)

        resolutions: List[Dict[str, Any]] = []
        for (actor, provision_type), group in groups.items():
            winner = group[0]
            suppressed = group[1:]
            resolutions.append(
                {
                    "group": {"actor": actor, "provision_type": provision_type},
                    "winner": winner.provision_id,
                    "winner_score": round(self._score(winner), 3),
                    "suppressed": [item.provision_id for item in suppressed],
                }
            )

        return {
            "resolved_at": datetime.utcnow().isoformat() + "Z",
            "ranked_signals": [signal.to_dict() for signal in ranked],
            "resolutions": resolutions,
        }

    def _score(self, signal: LegalSignal) -> float:
        jurisdiction = self.JURISDICTION_WEIGHT.get(signal.jurisdiction_level, 50)
        modality = self.MODALITY_WEIGHT.get(signal.modality, 12)
        signal_type = self.SIGNAL_TYPE_WEIGHT.get(signal.signal_type, 5)
        specificity = min(10.0, len(signal.conditions) * 1.5 + len(signal.exceptions) * 1.5)
        override_bonus = 6.0 if signal.overrides else 0.0
        certainty_penalty = min(5.0, len(signal.interpretive_terms) * 0.8)

        return (
            jurisdiction
            + modality
            + signal_type
            + specificity
            + override_bonus
            + (signal.strength * 12.0)
            - certainty_penalty
        )


legal_signal_extractor = LegalSignalExtractor()
precedence_engine = PrecedenceEngine()

__all__ = [
    "CitationSpan",
    "LegalSignal",
    "LegalSignalExtractor",
    "PrecedenceEngine",
    "legal_signal_extractor",
    "precedence_engine",
]
