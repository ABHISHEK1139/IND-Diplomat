"""
Layer-2 claim extraction.

Converts document text into structured claim units for contradiction/corroboration.
"""

from __future__ import annotations

from typing import Any, Dict, List
import re


POSITIVE_TOKENS = ("cooperate", "consult", "agree", "support", "de-escalat", "dialogue")
NEGATIVE_TOKENS = ("threat", "sanction", "attack", "mobiliz", "violate", "blockade")


class ClaimExtractor:
    def extract_from_document(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        text = str(document.get("content", "") or "").strip()
        if not text:
            return []
        metadata = dict(document.get("metadata", {}) or {})
        doc_id = str(document.get("id") or metadata.get("document_id") or "")
        date = str(metadata.get("date") or "")
        source = str(metadata.get("source") or "unknown")

        claims: List[Dict[str, Any]] = []
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for idx, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if len(sentence.split()) < 5:
                continue

            actor, target = self._extract_actor_target(sentence, metadata)
            predicate = self._extract_predicate(sentence)
            polarity = self._classify_polarity(sentence)
            confidence = 0.7 if predicate != "statement" else 0.5

            claims.append(
                {
                    "claim_id": f"{doc_id or 'doc'}_claim_{idx}",
                    "document_id": doc_id,
                    "actor": actor,
                    "target": target,
                    "predicate": predicate,
                    "polarity": polarity,
                    "claim_text": sentence,
                    "confidence": confidence,
                    "claim_date": date,
                    "metadata": {"source": source},
                }
            )
        return claims

    def extract_batch(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        claims: List[Dict[str, Any]] = []
        for doc in documents or []:
            claims.extend(self.extract_from_document(doc))
        return claims

    def _extract_actor_target(self, sentence: str, metadata: Dict[str, Any]):
        actors_raw = metadata.get("actors") or []
        if isinstance(actors_raw, str):
            actors = [part.strip() for part in actors_raw.split(",") if part.strip()]
        else:
            actors = list(actors_raw)
        if len(actors) >= 2:
            return str(actors[0]), str(actors[1])
        if len(actors) == 1:
            return str(actors[0]), ""

        # Fallback: first two capitalized tokens.
        entities = re.findall(r"\b[A-Z][A-Za-z]{2,}\b", sentence)
        if len(entities) >= 2:
            return entities[0], entities[1]
        if len(entities) == 1:
            return entities[0], ""
        return "", ""

    def _extract_predicate(self, sentence: str) -> str:
        lower = sentence.lower()
        for token in ("sanction", "threat", "mobiliz", "consult", "agree", "blockade", "warn"):
            if token in lower:
                return token
        return "statement"

    def _classify_polarity(self, sentence: str) -> str:
        lower = sentence.lower()
        if any(token in lower for token in NEGATIVE_TOKENS):
            return "negative"
        if any(token in lower for token in POSITIVE_TOKENS):
            return "positive"
        return "neutral"


claim_extractor = ClaimExtractor()

__all__ = ["ClaimExtractor", "claim_extractor"]
