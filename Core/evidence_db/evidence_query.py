"""
Query helpers for evidence database.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import sqlite3


class EvidenceQuery:
    def __init__(self, db_path: str = "data/evidence_store.db"):
        self._db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_claims_for_actor_pair(
        self,
        actor: str,
        target: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if target:
            sql = """
            SELECT * FROM claims
            WHERE actor = ? AND target = ?
            ORDER BY claim_date DESC
            LIMIT ?
            """
            params = (actor, target, int(limit))
        else:
            sql = """
            SELECT * FROM claims
            WHERE actor = ?
            ORDER BY claim_date DESC
            LIMIT ?
            """
            params = (actor, int(limit))

        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [self._row_to_claim(row) for row in rows]

    def get_legal_signals_for_document(self, document_id: str) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM legal_signals WHERE document_id = ?",
                (document_id,),
            ).fetchall()
        finally:
            conn.close()
        payload: List[Dict[str, Any]] = []
        for row in rows:
            payload.append(
                {
                    "signal_id": row["signal_id"],
                    "document_id": row["document_id"],
                    "provision_id": row["provision_id"],
                    "modality": row["modality"],
                    "signal_type": row["signal_type"],
                    "actor": row["actor"],
                    "strength": float(row["strength"]),
                    "conditions": json.loads(row["condition_json"] or "[]"),
                    "overrides": json.loads(row["override_json"] or "[]"),
                    "source_text": row["source_text"],
                    "metadata": json.loads(row["metadata_json"] or "{}"),
                }
            )
        return payload

    def _row_to_claim(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "claim_id": row["claim_id"],
            "document_id": row["document_id"],
            "actor": row["actor"],
            "target": row["target"],
            "predicate": row["predicate"],
            "polarity": row["polarity"],
            "claim_text": row["claim_text"],
            "confidence": float(row["confidence"]),
            "claim_date": row["claim_date"],
            "metadata": json.loads(row["metadata_json"] or "{}"),
        }


__all__ = ["EvidenceQuery"]
