"""
SQLite-backed storage for investigation cases.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import json
import sqlite3

from .case import CaseRecord, CaseStatus


class CaseStore:
    """
    Persistent case store.
    """

    def __init__(self, db_path: str = "data/case_store.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            actors_json TEXT NOT NULL,
            start_time TEXT NOT NULL,
            current_hypothesis TEXT NOT NULL,
            missing_evidence_json TEXT NOT NULL,
            evidence_ids_json TEXT NOT NULL,
            confidence REAL NOT NULL,
            status TEXT NOT NULL,
            analysis_history_json TEXT NOT NULL,
            rejected_hypotheses_json TEXT NOT NULL,
            search_history_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
        conn = self._connect()
        try:
            conn.execute(ddl)
            conn.commit()
        finally:
            conn.close()

    def upsert(self, record: CaseRecord) -> None:
        record.updated_at = datetime.utcnow().isoformat() + "Z"
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO cases (
                    case_id, question, actors_json, start_time, current_hypothesis,
                    missing_evidence_json, evidence_ids_json, confidence, status,
                    analysis_history_json, rejected_hypotheses_json, search_history_json,
                    metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    question=excluded.question,
                    actors_json=excluded.actors_json,
                    start_time=excluded.start_time,
                    current_hypothesis=excluded.current_hypothesis,
                    missing_evidence_json=excluded.missing_evidence_json,
                    evidence_ids_json=excluded.evidence_ids_json,
                    confidence=excluded.confidence,
                    status=excluded.status,
                    analysis_history_json=excluded.analysis_history_json,
                    rejected_hypotheses_json=excluded.rejected_hypotheses_json,
                    search_history_json=excluded.search_history_json,
                    metadata_json=excluded.metadata_json,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at;
                """,
                (
                    record.case_id,
                    record.question,
                    json.dumps(record.actors),
                    record.start_time,
                    record.current_hypothesis,
                    json.dumps(record.missing_evidence),
                    json.dumps(record.evidence_ids),
                    float(record.confidence),
                    str(record.status.value),
                    json.dumps(record.analysis_history),
                    json.dumps(record.rejected_hypotheses),
                    json.dumps(record.search_history),
                    json.dumps(record.metadata),
                    record.created_at,
                    record.updated_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get(self, case_id: str) -> Optional[CaseRecord]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM cases WHERE case_id = ?",
                (case_id,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return self._row_to_case(row)

    def list_recent(self, limit: int = 20) -> List[CaseRecord]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM cases ORDER BY updated_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_case(row) for row in rows]

    def _row_to_case(self, row: sqlite3.Row) -> CaseRecord:
        return CaseRecord(
            case_id=row["case_id"],
            question=row["question"],
            actors=json.loads(row["actors_json"] or "[]"),
            start_time=row["start_time"],
            current_hypothesis=row["current_hypothesis"] or "",
            missing_evidence=json.loads(row["missing_evidence_json"] or "[]"),
            evidence_ids=json.loads(row["evidence_ids_json"] or "[]"),
            confidence=float(row["confidence"] or 0.0),
            status=CaseStatus(row["status"]),
            analysis_history=json.loads(row["analysis_history_json"] or "[]"),
            rejected_hypotheses=json.loads(row["rejected_hypotheses_json"] or "[]"),
            search_history=json.loads(row["search_history_json"] or "[]"),
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
