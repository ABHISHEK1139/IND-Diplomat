"""
Layer-2 knowledge ingestor.

Bridge stage:
documents from investigation -> extraction -> persistent stores/indexes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urlparse
import hashlib

from Core.database.db import Base, engine
from Core.database.models import Document, Statement
from Core.database.session import get_session
from Core.evidence_db.evidence_store import evidence_store
from engine.Layer2_Knowledge.claim_extractor import claim_extractor
from engine.Layer2_Knowledge.information_value import information_value
from engine.Layer2_Knowledge.legal_signal_extractor import legal_signal_extractor
from engine.Layer2_Knowledge.multi_index import multi_index_manager
from engine.Layer2_Knowledge.signal_deduplicator import signal_signature


@dataclass
class IngestionSummary:
    documents_received: int = 0
    documents_indexed: int = 0
    documents_persisted: int = 0
    statements_added: int = 0
    claims_added: int = 0
    legal_signals_added: int = 0
    duplicate_legal_signals: int = 0
    new_information: float = 0.0
    effective_information: float = 0.0
    existing_information: float = 0.0
    total_information: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "documents_received": self.documents_received,
            "documents_indexed": self.documents_indexed,
            "documents_persisted": self.documents_persisted,
            "statements_added": self.statements_added,
            "claims_added": self.claims_added,
            "legal_signals_added": self.legal_signals_added,
            "duplicate_legal_signals": self.duplicate_legal_signals,
            "new_information": round(float(self.new_information), 6),
            "effective_information": round(float(self.effective_information), 6),
            "existing_information": round(float(self.existing_information), 6),
            "total_information": round(float(self.total_information), 6),
        }


def ingest_documents(documents: List[Dict[str, Any]]) -> IngestionSummary:
    """
    Persist newly collected investigation documents into Layer-2 stores.
    """
    summary = IngestionSummary(documents_received=len(documents or []))
    existing_info = evidence_store.total_information()
    existing_signal_floor = evidence_store.count_legal_signals() * 0.05
    summary.existing_information = max(existing_info, existing_signal_floor)
    normalized_docs = [_normalize_document(doc) for doc in (documents or [])]
    normalized_docs = [doc for doc in normalized_docs if str(doc.get("content", "")).strip()]
    if not normalized_docs:
        return summary

    # 1) Commit to Layer-2 indexes for future retrieval.
    multi_index_manager.initialize()
    multi_index_manager.add_documents(normalized_docs)
    summary.documents_indexed = len(normalized_docs)

    # 2) Commit extracted structures to persistent stores.
    Base.metadata.create_all(bind=engine)
    db = get_session()
    try:
        existing_stmt_keys = {
            (row.actor, row.target, row.action, row.timestamp)
            for row in db.query(Statement.actor, Statement.target, Statement.action, Statement.timestamp).all()
        }
        batch_signal_signatures = set()

        for doc in normalized_docs:
            doc_model = _upsert_document_row(db, doc)
            if doc_model is not None:
                summary.documents_persisted += 1

            evidence_doc_id = evidence_store.upsert_document(doc)

            claims = claim_extractor.extract_from_document(doc)
            for claim in claims:
                claim_payload = dict(claim)
                claim_payload["document_id"] = evidence_doc_id
                evidence_store.insert_claim(claim_payload)
                summary.claims_added += 1

                actor = _normalize_actor_label(claim_payload.get("actor", ""))
                target = _normalize_actor_label(claim_payload.get("target", ""))
                if not actor or not target or actor == target:
                    continue
                action = _predicate_to_action(str(claim_payload.get("predicate", "statement")))
                timestamp = str(claim_payload.get("claim_date") or doc["metadata"].get("date") or _today())[:10]
                stmt_key = (actor, target, action, timestamp)
                if stmt_key in existing_stmt_keys:
                    continue

                db.add(
                    Statement(
                        actor=actor,
                        target=target,
                        action=action,
                        tone=_polarity_to_tone(str(claim_payload.get("polarity", "neutral"))),
                        document_id=doc_model.id if doc_model else None,
                        timestamp=timestamp,
                    )
                )
                existing_stmt_keys.add(stmt_key)
                summary.statements_added += 1

            signals = legal_signal_extractor.extract_from_documents([doc])
            for signal in signals:
                signal_payload = signal.to_dict()
                actor = _normalize_actor_label(signal_payload.get("actor", ""))
                signature = str(signal_payload.get("signature") or "").strip()
                if not signature:
                    signature = signal_signature(
                        actor or "unknown",
                        str(signal_payload.get("signal_type", "NONE")),
                        str(signal_payload.get("original_text", "")),
                    )

                is_duplicate = (
                    signature in batch_signal_signatures
                    or evidence_store.has_legal_signal_signature(signature)
                )
                signal_payload["signature"] = signature
                signal_payload["is_duplicate"] = is_duplicate
                signal_payload["source_domain"] = _domain_from_url(str(doc.get("url") or "")) or str(
                    doc.get("metadata", {}).get("source", "")
                )
                signal_payload["signal_date"] = str(doc.get("metadata", {}).get("date") or _today())[:10]
                signal_payload["source"] = signal_payload["source_domain"] or str(
                    doc.get("metadata", {}).get("source", "")
                )
                signal_payload["date"] = signal_payload["signal_date"]
                signal_payload["information_value"] = information_value(signal_payload)
                summary.effective_information += float(signal_payload["information_value"])

                if is_duplicate:
                    summary.duplicate_legal_signals += 1
                    batch_signal_signatures.add(signature)
                    continue

                evidence_store.insert_legal_signal(evidence_doc_id, signal_payload)
                summary.legal_signals_added += 1
                summary.new_information += float(signal_payload["information_value"])
                batch_signal_signatures.add(signature)

        db.commit()
    finally:
        db.close()

    summary.total_information = summary.existing_information + summary.effective_information
    return summary


def _upsert_document_row(db, doc: Dict[str, Any]):
    metadata = doc.get("metadata", {}) or {}
    url = str(doc.get("url") or metadata.get("url") or "")
    title = str(doc.get("title") or metadata.get("title") or "")[:500]
    published_date = str(metadata.get("date") or _today())[:10]
    source_domain = _domain_from_url(url) or str(metadata.get("source") or "unknown")
    credibility = _source_credibility(str(metadata.get("source") or "unknown"))

    existing = None
    if url:
        existing = db.query(Document).filter(Document.url == url).first()
    if existing is None and title and published_date:
        existing = (
            db.query(Document)
            .filter(Document.title == title, Document.published_date == published_date)
            .first()
        )

    if existing:
        existing.source_domain = source_domain
        existing.title = title
        existing.published_date = published_date
        existing.credibility = credibility
        db.flush()
        return existing

    row = Document(
        url=url,
        source_domain=source_domain,
        title=title,
        published_date=published_date,
        credibility=credibility,
    )
    db.add(row)
    db.flush()
    return row


def _normalize_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    raw_meta = dict(doc.get("metadata") or {})
    content = str(doc.get("content") or doc.get("text") or "").strip()
    url = str(doc.get("url") or doc.get("source_url") or raw_meta.get("url") or "").strip()
    title = str(doc.get("title") or raw_meta.get("title") or "").strip()
    date = str(
        doc.get("date")
        or raw_meta.get("date")
        or raw_meta.get("published_at")
        or raw_meta.get("collected_at")
        or _today()
    )[:10]
    doc_type = str(
        raw_meta.get("type")
        or doc.get("statement_type")
        or "news"
    ).strip().lower()

    actors = raw_meta.get("actors") or []
    if isinstance(actors, str):
        actors = [part.strip() for part in actors.split(",") if part.strip()]
    elif not isinstance(actors, list):
        actors = []

    country = _normalize_actor_label(str(doc.get("country") or raw_meta.get("country") or ""))
    target_country = _normalize_actor_label(str(doc.get("target_country") or raw_meta.get("target_country") or ""))
    if country and country not in actors:
        actors.append(country)
    if target_country and target_country not in actors:
        actors.append(target_country)

    source = str(raw_meta.get("source") or "moltbot_scrape").strip().lower()
    canonical_id = str(doc.get("id") or _stable_doc_id(url, content, source))

    metadata = dict(raw_meta)
    metadata["source"] = source
    metadata["type"] = doc_type
    metadata["date"] = date
    metadata["actors"] = actors
    if url:
        metadata["url"] = url

    return {
        "id": canonical_id,
        "title": title,
        "url": url,
        "content": content,
        "metadata": metadata,
    }


def _stable_doc_id(url: str, content: str, source: str) -> str:
    seed = f"{source}|{url}|{content[:300]}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
    return f"ing_{digest}"


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        return urlparse(url).netloc.lower().strip()
    except Exception:
        return ""


def _source_credibility(source: str) -> float:
    text = str(source or "").lower()
    if "government" in text or "ministry" in text or ".gov" in text:
        return 0.90
    if "reuters" in text or "ap" in text or "bbc" in text:
        return 0.80
    if "archive" in text:
        return 0.65
    return 0.60


def _normalize_actor_label(actor: str) -> str:
    text = str(actor or "").strip()
    if not text:
        return ""
    key = text.lower()
    if key in {"usa", "united states", "u.s.", "us"}:
        return "USA"
    if key in {"china", "chn", "prc"}:
        return "China"
    if key in {"taiwan", "twn"}:
        return "Taiwan"
    if len(text) == 3 and text.isalpha():
        return text.upper()
    return text


def _predicate_to_action(predicate: str) -> str:
    key = str(predicate or "").strip().lower()
    if not key:
        return "statement"
    mapping = {
        "threat": "threatened",
        "warn": "warned",
        "sanction": "sanctioned",
        "mobiliz": "mobilized",
        "consult": "consulted",
        "agree": "agreed",
        "blockade": "blockaded",
    }
    for token, action in mapping.items():
        if token in key:
            return action
    return key if len(key) <= 40 else "statement"


def _polarity_to_tone(polarity: str) -> float:
    text = str(polarity or "").lower()
    if text == "negative":
        return -0.6
    if text == "positive":
        return 0.6
    return 0.0


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


__all__ = ["IngestionSummary", "ingest_documents"]
