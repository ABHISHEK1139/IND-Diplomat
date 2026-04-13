"""
Evidence sufficiency gate.

Prevents reasoning when evidence quality is below minimum thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence


PRIMARY_SOURCE_HINTS = {
    "treaties",
    "un_resolutions",
    "sanctions_lists",
    "govt_statements",
    "world_bank",
    "un_comtrade",
    "imf",
    "sipri",
}

HOSTILE_PREDICATES = {
    "threat",
    "warn",
    "attack",
    "mobilize",
    "sanction",
    "blockade",
    "war",
    "coerce",
    "pressure",
    "fight",
    "violate",
}

_ACTOR_ALIASES = {
    "USA": "USA",
    "US": "USA",
    "UNITEDSTATES": "USA",
    "AMERICA": "USA",
    "CHINA": "CHINA",
    "CHN": "CHINA",
    "PRC": "CHINA",
    "TAIWAN": "TAIWAN",
    "TWN": "TAIWAN",
    "BRAZIL": "BRAZIL",
    "BRA": "BRAZIL",
    "CANADA": "CANADA",
    "CAN": "CANADA",
}

_PREDICATE_ROOTS = {
    "threat": "threat",
    "warn": "warn",
    "attack": "attack",
    "mobiliz": "mobilize",
    "sanction": "sanction",
    "blockad": "blockade",
    "war": "war",
    "coerc": "coerce",
    "pressur": "pressure",
    "fight": "fight",
    "violat": "violate",
}


@dataclass
class EvidenceGateResult:
    passed: bool
    score: float
    independent_source_count: int
    has_primary_source: bool
    recency_ok: bool
    requirement_coverage: float
    gaps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "score": round(self.score, 4),
            "independent_source_count": self.independent_source_count,
            "has_primary_source": self.has_primary_source,
            "recency_ok": self.recency_ok,
            "requirement_coverage": round(self.requirement_coverage, 4),
            "gaps": list(self.gaps),
        }


class EvidenceGate:
    def __init__(
        self,
        min_independent_sources: int = 2,
        max_age_days: int = 30,
    ):
        self.min_independent_sources = int(min_independent_sources)
        self.max_age_days = int(max_age_days)

    def evaluate(
        self,
        documents: Sequence[Dict[str, Any]],
        required_evidence: Iterable[Any],
        claims: Optional[Sequence[Dict[str, Any]]] = None,
        claim_constraints: Optional[Dict[str, Any]] = None,
    ) -> EvidenceGateResult:
        docs = list(documents or [])
        claims_list = list(claims or [])
        required = [self._normalize_requirement(item) for item in required_evidence or []]
        gaps: List[str] = []

        if not claims_list:
            claims_list = self._derive_claims_from_documents(docs)

        normalized_constraints = self._normalize_claim_constraints(claim_constraints)
        matched_claims = claims_list
        effective_docs = docs
        claim_match_ok = True

        if normalized_constraints:
            matched_claims = self._filter_claims(claims_list, normalized_constraints)
            claim_match_ok = len(matched_claims) > 0
            if not claim_match_ok:
                gaps.append("No claim-level evidence matches required actors/actions")
                effective_docs = []
            else:
                effective_docs = self._filter_documents_for_claims(
                    docs=docs,
                    matched_claims=matched_claims,
                    constraints=normalized_constraints,
                )
                if not effective_docs:
                    gaps.append("No documents linked to matching claims")

        sources = {self._source_name(doc) for doc in effective_docs if self._source_name(doc)}
        source_count = len(sources)
        if source_count < self.min_independent_sources:
            gaps.append(
                f"Need at least {self.min_independent_sources} independent sources, got {source_count}"
            )

        has_primary = any(source in PRIMARY_SOURCE_HINTS for source in sources)
        if not has_primary:
            gaps.append("Missing primary source evidence")

        recency_ok = self._check_recency(effective_docs)
        if not recency_ok:
            gaps.append(f"Evidence too old; require newer than {self.max_age_days} days")

        coverage = self._requirement_coverage(effective_docs, required)
        if coverage < 1.0 and required:
            gaps.append("Not all required evidence classes are covered")

        # Weighted gate score tuned to prioritize source diversity and coverage.
        source_score = min(1.0, source_count / float(self.min_independent_sources))
        primary_score = 1.0 if has_primary else 0.0
        recency_score = 1.0 if recency_ok else 0.0
        claim_score = 1.0 if claim_match_ok else 0.0
        score = (
            0.35 * source_score
            + 0.2 * primary_score
            + 0.2 * recency_score
            + 0.15 * coverage
            + 0.1 * claim_score
        )
        passed = (
            source_score >= 1.0
            and has_primary
            and recency_ok
            and coverage >= 1.0
            and claim_match_ok
        )

        return EvidenceGateResult(
            passed=passed,
            score=score,
            independent_source_count=source_count,
            has_primary_source=has_primary,
            recency_ok=recency_ok,
            requirement_coverage=coverage,
            gaps=gaps,
        )

    def _normalize_requirement(self, req: Any) -> str:
        text = str(getattr(req, "value", req) or "").strip().lower()
        return text

    def _normalize_actor(self, value: Any) -> str:
        text = str(value or "").strip().upper()
        cleaned = re.sub(r"[^A-Z0-9]", "", text)
        return _ACTOR_ALIASES.get(cleaned, cleaned)

    def _normalize_predicate(self, predicate: Any, claim_text: str = "") -> str:
        text = str(predicate or "").strip().lower()
        for root, canonical in _PREDICATE_ROOTS.items():
            if root in text:
                return canonical

        claim_lower = str(claim_text or "").lower()
        for root, canonical in _PREDICATE_ROOTS.items():
            if root in claim_lower:
                return canonical
        return text or "statement"

    def _normalize_claim_constraints(self, constraints: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not constraints:
            return {}

        actor_a = ""
        actor_b = ""
        actors = constraints.get("actors")
        if isinstance(actors, (list, tuple)) and len(actors) >= 2:
            actor_a, actor_b = actors[0], actors[1]

        actor_a = constraints.get("actor_a", constraints.get("actor", actor_a))
        actor_b = constraints.get("actor_b", constraints.get("target", actor_b))
        actor_a_norm = self._normalize_actor(actor_a) if actor_a else ""
        actor_b_norm = self._normalize_actor(actor_b) if actor_b else ""

        action_values = constraints.get("actions", []) or []
        normalized_actions = {
            self._normalize_predicate(action)
            for action in action_values
            if str(action or "").strip()
        }
        if constraints.get("hostile_only") or constraints.get("hostile"):
            normalized_actions.update(HOSTILE_PREDICATES)

        return {
            "actor_a": actor_a_norm,
            "actor_b": actor_b_norm,
            "directed": bool(constraints.get("directed", True)),
            "actions": normalized_actions,
        }

    def _derive_claims_from_documents(self, docs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        claims: List[Dict[str, Any]] = []
        for doc in docs:
            metadata = doc.get("metadata", {}) or {}
            doc_id = str(doc.get("id") or metadata.get("document_id") or metadata.get("obs_id") or "")
            actors = self._extract_document_actors(doc)
            actor = actors[0] if len(actors) > 0 else ""
            target = actors[1] if len(actors) > 1 else ""
            claim_text = str(doc.get("content", "") or "")
            predicate = self._normalize_predicate(
                metadata.get("action") or metadata.get("event_type") or "",
                claim_text=claim_text,
            )
            claims.append(
                {
                    "claim_id": f"{doc_id or 'doc'}_derived",
                    "document_id": doc_id,
                    "actor": actor,
                    "target": target,
                    "predicate": predicate,
                    "claim_text": claim_text,
                    "metadata": {"source": self._source_name(doc)},
                }
            )
        return claims

    def _extract_document_actors(self, doc: Dict[str, Any]) -> List[str]:
        metadata = doc.get("metadata", {}) or {}
        actors = metadata.get("actors", [])
        if isinstance(actors, str):
            actors = [token.strip() for token in actors.split(",") if token.strip()]
        if not isinstance(actors, list):
            actors = []

        normalized = [self._normalize_actor(actor) for actor in actors if str(actor or "").strip()]
        if len(normalized) >= 2:
            return normalized[:2]

        # Fallback: infer from content title-case entities.
        content = str(doc.get("content", "") or "")
        entities = re.findall(r"\b[A-Z][A-Za-z]{2,}\b", content)
        inferred = [self._normalize_actor(entity) for entity in entities]
        merged = normalized + [entity for entity in inferred if entity not in normalized]
        return merged[:2]

    def _filter_claims(self, claims: Sequence[Dict[str, Any]], constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
        matched: List[Dict[str, Any]] = []
        for claim in claims:
            actor = self._normalize_actor(claim.get("actor"))
            target = self._normalize_actor(claim.get("target"))
            predicate = self._normalize_predicate(claim.get("predicate"), claim_text=claim.get("claim_text", ""))

            if not self._claim_matches_actor_pair(actor, target, constraints):
                continue

            required_actions = constraints.get("actions", set())
            if required_actions and predicate not in required_actions:
                continue

            matched.append(claim)
        return matched

    def _claim_matches_actor_pair(self, actor: str, target: str, constraints: Dict[str, Any]) -> bool:
        actor_a = constraints.get("actor_a", "")
        actor_b = constraints.get("actor_b", "")
        if not actor_a and not actor_b:
            return True
        if not actor or not target:
            return False

        if constraints.get("directed", True):
            return actor == actor_a and target == actor_b

        return {actor, target} == {actor_a, actor_b}

    def _filter_documents_for_claims(
        self,
        docs: Sequence[Dict[str, Any]],
        matched_claims: Sequence[Dict[str, Any]],
        constraints: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        claim_doc_ids = {
            str(claim.get("document_id") or "").strip()
            for claim in matched_claims
            if str(claim.get("document_id") or "").strip()
        }
        if claim_doc_ids:
            filtered = []
            for doc in docs:
                meta = doc.get("metadata", {}) or {}
                doc_id = str(doc.get("id") or meta.get("document_id") or meta.get("obs_id") or "").strip()
                if doc_id in claim_doc_ids:
                    filtered.append(doc)
            if filtered:
                return filtered

        actor_a = constraints.get("actor_a", "")
        actor_b = constraints.get("actor_b", "")
        if actor_a and actor_b:
            return [
                doc for doc in docs
                if self._document_mentions_actor_pair(doc, actor_a, actor_b, constraints.get("directed", True))
            ]
        return list(docs)

    def _document_mentions_actor_pair(
        self,
        doc: Dict[str, Any],
        actor_a: str,
        actor_b: str,
        directed: bool,
    ) -> bool:
        actors = self._extract_document_actors(doc)
        if len(actors) >= 2:
            left, right = actors[0], actors[1]
            if directed:
                return left == actor_a and right == actor_b
            return {left, right} == {actor_a, actor_b}
        return False

    def _source_name(self, doc: Dict[str, Any]) -> str:
        meta = doc.get("metadata", {}) or {}
        return str(meta.get("source") or "").strip().lower()

    def _doc_type(self, doc: Dict[str, Any]) -> str:
        meta = doc.get("metadata", {}) or {}
        return str(meta.get("type") or "").strip().lower()

    def _date_str(self, doc: Dict[str, Any]) -> str:
        meta = doc.get("metadata", {}) or {}
        return str(meta.get("date") or meta.get("published_at") or "").strip()

    def _check_recency(self, docs: Sequence[Dict[str, Any]]) -> bool:
        if not docs:
            return False
        now = datetime.utcnow()
        seen_any = False
        for doc in docs:
            raw = self._date_str(doc)
            if not raw:
                continue
            parsed = self._parse_date(raw)
            if not parsed:
                continue
            seen_any = True
            age_days = (now - parsed).total_seconds() / 86400.0
            if age_days <= self.max_age_days:
                return True
        # If no valid dates are present, treat as not recency-verified.
        return False

    def _requirement_coverage(self, docs: Sequence[Dict[str, Any]], required: List[str]) -> float:
        if not required:
            return 1.0
        available = {self._doc_type(doc) for doc in docs}
        if not available:
            return 0.0

        mapping = {
            "treaty_text": {"treaty", "legal"},
            "legal_provision": {"legal", "law"},
            "official_statement": {"statement", "press_release"},
            "news_report": {"news", "report", "article"},
            "statistical_data": {"data", "statistics", "economic", "report"},
            "historical_record": {"historical", "archive", "record"},
            "expert_analysis": {"analysis", "research", "report"},
        }
        matched = 0
        for req in required:
            allowed = mapping.get(req, {req})
            if any(item in available for item in allowed):
                matched += 1
        return matched / float(len(required))

    def _parse_date(self, raw: str):
        text = raw.strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
            try:
                return datetime.strptime(text[:10], fmt)
            except ValueError:
                continue
        return None


evidence_gate = EvidenceGate()

def check_evidence_sufficiency(
    documents: Sequence[Dict[str, Any]],
    required_evidence: Iterable[Any],
    claims: Optional[Sequence[Dict[str, Any]]] = None,
    claim_constraints: Optional[Dict[str, Any]] = None,
) -> bool:
    return evidence_gate.evaluate(
        documents=documents,
        required_evidence=required_evidence,
        claims=claims,
        claim_constraints=claim_constraints,
    ).passed


__all__ = ["EvidenceGate", "EvidenceGateResult", "evidence_gate", "check_evidence_sufficiency"]
