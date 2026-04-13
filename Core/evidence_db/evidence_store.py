"""
Evidence store: normalized persistence for document-level evidence units.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import hashlib
import json
import sqlite3
import uuid


class EvidenceStore:
    """
    SQLite evidence database.
    """

    def __init__(
        self,
        db_path: str = "data/evidence_store.db",
        schema_path: Optional[str] = None,
    ):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        if schema_path is None:
            schema_path = str(Path(__file__).with_name("schema.sql"))
        self._schema_path = Path(schema_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        schema_sql = self._schema_path.read_text(encoding="utf-8")
        conn = self._connect()
        try:
            conn.executescript(schema_sql)
            conn.commit()
        finally:
            conn.close()

    def upsert_document(self, document: Dict[str, Any]) -> str:
        metadata = dict(document.get("metadata", {}) or {})
        doc_id = str(document.get("id") or self._stable_doc_id(document))
        source = str(metadata.get("source") or "unknown")
        doc_type = str(metadata.get("type") or "unknown")
        title = str(metadata.get("title") or "")
        content = str(document.get("content") or "")
        if not content.strip():
            return doc_id
        published_at = str(metadata.get("date") or metadata.get("published_at") or "")
        ingested_at = datetime.utcnow().isoformat() + "Z"

        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO documents (
                    document_id, source, doc_type, title, content, published_at, ingested_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    source=excluded.source,
                    doc_type=excluded.doc_type,
                    title=excluded.title,
                    content=excluded.content,
                    published_at=excluded.published_at,
                    ingested_at=excluded.ingested_at,
                    metadata_json=excluded.metadata_json;
                """,
                (
                    doc_id,
                    source,
                    doc_type,
                    title,
                    content,
                    published_at,
                    ingested_at,
                    json.dumps(metadata),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return doc_id

    def upsert_documents(self, documents: Iterable[Dict[str, Any]]) -> List[str]:
        ids: List[str] = []
        for doc in documents:
            ids.append(self.upsert_document(doc))
        return ids

    def insert_claim(self, claim: Dict[str, Any]) -> str:
        claim_id = str(claim.get("claim_id") or f"clm_{uuid.uuid4().hex[:12]}")
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO claims (
                    claim_id, document_id, actor, target, predicate, polarity,
                    claim_text, confidence, claim_date, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(claim_id) DO UPDATE SET
                    document_id=excluded.document_id,
                    actor=excluded.actor,
                    target=excluded.target,
                    predicate=excluded.predicate,
                    polarity=excluded.polarity,
                    claim_text=excluded.claim_text,
                    confidence=excluded.confidence,
                    claim_date=excluded.claim_date,
                    metadata_json=excluded.metadata_json;
                """,
                (
                    claim_id,
                    str(claim.get("document_id") or ""),
                    str(claim.get("actor") or ""),
                    str(claim.get("target") or ""),
                    str(claim.get("predicate") or "statement"),
                    str(claim.get("polarity") or "neutral"),
                    str(claim.get("claim_text") or ""),
                    float(claim.get("confidence", 0.5)),
                    str(claim.get("claim_date") or ""),
                    json.dumps(dict(claim.get("metadata") or {})),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return claim_id

    def insert_event(self, event: Dict[str, Any]) -> str:
        event_id = str(event.get("event_id") or f"evt_{uuid.uuid4().hex[:12]}")
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO events (
                    event_id, document_id, actor_a, actor_b, event_type,
                    event_date, intensity, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    document_id=excluded.document_id,
                    actor_a=excluded.actor_a,
                    actor_b=excluded.actor_b,
                    event_type=excluded.event_type,
                    event_date=excluded.event_date,
                    intensity=excluded.intensity,
                    metadata_json=excluded.metadata_json;
                """,
                (
                    event_id,
                    str(event.get("document_id") or ""),
                    str(event.get("actor_a") or ""),
                    str(event.get("actor_b") or ""),
                    str(event.get("event_type") or "unknown"),
                    str(event.get("event_date") or ""),
                    float(event.get("intensity", 0.5)),
                    json.dumps(dict(event.get("metadata") or {})),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return event_id

    def insert_statement(self, statement: Dict[str, Any]) -> str:
        statement_id = str(statement.get("statement_id") or f"stmt_{uuid.uuid4().hex[:12]}")
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO statements (
                    statement_id, document_id, speaker, audience, tone, text,
                    statement_date, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(statement_id) DO UPDATE SET
                    document_id=excluded.document_id,
                    speaker=excluded.speaker,
                    audience=excluded.audience,
                    tone=excluded.tone,
                    text=excluded.text,
                    statement_date=excluded.statement_date,
                    metadata_json=excluded.metadata_json;
                """,
                (
                    statement_id,
                    str(statement.get("document_id") or ""),
                    str(statement.get("speaker") or ""),
                    str(statement.get("audience") or ""),
                    float(statement.get("tone", 0.0)),
                    str(statement.get("text") or ""),
                    str(statement.get("statement_date") or ""),
                    json.dumps(dict(statement.get("metadata") or {})),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return statement_id

    def insert_legal_signal(
        self,
        document_id: str,
        signal: Dict[str, Any],
    ) -> str:
        signal_id = str(signal.get("signal_id") or f"sig_{uuid.uuid4().hex[:12]}")
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO legal_signals (
                    signal_id, document_id, provision_id, modality, signal_type, actor,
                    strength, condition_json, override_json, source_text, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(signal_id) DO UPDATE SET
                    document_id=excluded.document_id,
                    provision_id=excluded.provision_id,
                    modality=excluded.modality,
                    signal_type=excluded.signal_type,
                    actor=excluded.actor,
                    strength=excluded.strength,
                    condition_json=excluded.condition_json,
                    override_json=excluded.override_json,
                    source_text=excluded.source_text,
                    metadata_json=excluded.metadata_json;
                """,
                (
                    signal_id,
                    document_id,
                    str(signal.get("provision_id") or ""),
                    str(signal.get("modality") or "may"),
                    str(signal.get("signal_type") or "NONE"),
                    str(signal.get("actor") or "unknown"),
                    float(signal.get("strength", 0.0)),
                    json.dumps(list(signal.get("conditions") or [])),
                    json.dumps(list(signal.get("overrides") or [])),
                    str(signal.get("original_text") or ""),
                    json.dumps(
                        {
                            "exceptions": list(signal.get("exceptions") or []),
                            "cross_refs": list(signal.get("cross_refs") or []),
                            "jurisdiction_level": signal.get("jurisdiction_level"),
                            "review_required": bool(signal.get("review_required", False)),
                            "signature": str(signal.get("signature") or ""),
                            "information_value": float(signal.get("information_value", 0.0) or 0.0),
                            "is_duplicate": bool(signal.get("is_duplicate", False)),
                            "source_domain": str(signal.get("source_domain") or ""),
                            "signal_date": str(signal.get("signal_date") or ""),
                        }
                    ),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return signal_id

    def has_legal_signal_signature(self, signature: str) -> bool:
        text = str(signature or "").strip()
        if not text:
            return False

        conn = self._connect()
        try:
            try:
                row = conn.execute(
                    """
                    SELECT 1
                    FROM legal_signals
                    WHERE json_extract(metadata_json, '$.signature') = ?
                    LIMIT 1
                    """,
                    (text,),
                ).fetchone()
                if row is not None:
                    return True
            except sqlite3.OperationalError:
                # Fallback when JSON functions are unavailable.
                pattern = f'%\"signature\": \"{text}\"%'
                row = conn.execute(
                    """
                    SELECT 1
                    FROM legal_signals
                    WHERE metadata_json LIKE ?
                    LIMIT 1
                    """,
                    (pattern,),
                ).fetchone()
                if row is not None:
                    return True
        finally:
            conn.close()
        return False

    def total_information(self) -> float:
        conn = self._connect()
        total = 0.0
        try:
            try:
                row = conn.execute(
                    """
                    SELECT COALESCE(SUM(CAST(json_extract(metadata_json, '$.information_value') AS REAL)), 0.0) AS total
                    FROM legal_signals
                    """
                ).fetchone()
                total = float((row["total"] if row else 0.0) or 0.0)
            except sqlite3.OperationalError:
                # Fallback parser when JSON functions are unavailable.
                rows = conn.execute("SELECT metadata_json FROM legal_signals").fetchall()
                for row in rows:
                    try:
                        payload = json.loads(row["metadata_json"] or "{}")
                    except Exception:
                        payload = {}
                    total += float(payload.get("information_value", 0.0) or 0.0)
        finally:
            conn.close()
        return round(total, 6)

    def count_legal_signals(self) -> int:
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) AS total FROM legal_signals").fetchone()
            return int((row["total"] if row else 0) or 0)
        finally:
            conn.close()

    def list_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT document_id, source, doc_type, title, content, published_at, ingested_at, metadata_json
                FROM documents
                ORDER BY ingested_at DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        finally:
            conn.close()
        payload: List[Dict[str, Any]] = []
        for row in rows:
            payload.append(
                {
                    "document_id": row["document_id"],
                    "source": row["source"],
                    "doc_type": row["doc_type"],
                    "title": row["title"],
                    "content": row["content"],
                    "published_at": row["published_at"],
                    "ingested_at": row["ingested_at"],
                    "metadata": json.loads(row["metadata_json"] or "{}"),
                }
            )
        return payload

    def _stable_doc_id(self, document: Dict[str, Any]) -> str:
        content = str(document.get("content") or "")
        metadata = dict(document.get("metadata", {}) or {})
        source = str(metadata.get("source") or "unknown")
        seed = f"{source}:{content[:500]}"
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
        return f"doc_{digest}"


evidence_store = EvidenceStore()

__all__ = ["EvidenceStore", "evidence_store"]
