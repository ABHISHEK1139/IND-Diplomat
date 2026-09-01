"""
Investigation Memory — SQLite Index + File-System Store
========================================================

The SQLite DB is an INDEX for fast queries (list, filter, search).
The InvestigationStore (file-system) is the SOURCE OF TRUTH.

This module bridges both: write to store + update index.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import create_engine, Column, String, Integer, Text
from sqlalchemy.orm import sessionmaker, declarative_base

from dip.core.schema import Investigation
from dip.core.investigation_store import InvestigationStore

logger = logging.getLogger("Memory.InvestigationMemory")

Base = declarative_base()


class InvestigationIndex(Base):
    """SQLite index row — lightweight metadata for fast queries."""
    __tablename__ = "investigations"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    original_query = Column(String, nullable=False)
    status = Column(String, default="CREATED")
    owner = Column(String, default="default")
    priority = Column(String, default="Medium")
    tags = Column(Text, default="[]")       # JSON array of strings
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    version = Column(Integer, default=1)


class InvestigationMemory:
    """
    Unified persistence layer.

    - Writes full Investigation to disk via InvestigationStore.
    - Maintains a lightweight SQLite index for fast list/filter/search.
    """

    def __init__(self, db_path: str = "investigations.db", store_root: str = "investigations"):
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.store = InvestigationStore(root_dir=store_root)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save_investigation(self, inv: Investigation) -> None:
        """Save to disk (source of truth) and update the SQLite index."""
        # 1. Persist to file system
        self.store.save(inv)

        # 2. Update SQLite index
        session = self.Session()
        try:
            existing = session.query(InvestigationIndex).filter_by(id=inv.investigation_id).first()
            if existing:
                existing.title = inv.title
                existing.status = inv.status
                existing.owner = inv.owner
                existing.priority = inv.priority
                existing.tags = json.dumps(inv.tags)
                existing.updated_at = datetime.now(timezone.utc).isoformat()
                existing.version = inv.version
            else:
                new_row = InvestigationIndex(
                    id=inv.investigation_id,
                    title=inv.title,
                    original_query=inv.original_query,
                    status=inv.status,
                    owner=inv.owner,
                    priority=inv.priority,
                    tags=json.dumps(inv.tags),
                    created_at=inv.created_at,
                    updated_at=inv.updated_at,
                    version=inv.version,
                )
                session.add(new_row)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update index: {e}")
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_investigation(self, investigation_id: str) -> Optional[Investigation]:
        """Load from disk (source of truth)."""
        return self.store.load(investigation_id)

    # Backward compatibility alias
    load_investigation = get_investigation

    def list_all(self) -> List[Investigation]:
        """List all investigations from the index, loading full objects from disk."""
        session = self.Session()
        try:
            rows = session.query(InvestigationIndex).order_by(InvestigationIndex.created_at.desc()).all()
            results = []
            for row in rows:
                inv = self.store.load(row.id)
                if inv:
                    results.append(inv)
            return results
        finally:
            session.close()

    def list_active_investigations(self) -> List[Investigation]:
        """List investigations that are not ARCHIVED."""
        session = self.Session()
        try:
            rows = (
                session.query(InvestigationIndex)
                .filter(InvestigationIndex.status != "ARCHIVED")
                .order_by(InvestigationIndex.created_at.desc())
                .all()
            )
            results = []
            for row in rows:
                inv = self.store.load(row.id)
                if inv:
                    results.append(inv)
            return results
        finally:
            session.close()

    def list_by_status(self, status: str) -> List[Investigation]:
        """List investigations by status."""
        session = self.Session()
        try:
            rows = (
                session.query(InvestigationIndex)
                .filter_by(status=status)
                .order_by(InvestigationIndex.created_at.desc())
                .all()
            )
            results = []
            for row in rows:
                inv = self.store.load(row.id)
                if inv:
                    results.append(inv)
            return results
        finally:
            session.close()

    def search(self, query: str) -> List[Investigation]:
        """Simple text search across title and original query."""
        session = self.Session()
        try:
            pattern = f"%{query}%"
            rows = (
                session.query(InvestigationIndex)
                .filter(
                    InvestigationIndex.title.like(pattern)
                    | InvestigationIndex.original_query.like(pattern)
                )
                .all()
            )
            results = []
            for row in rows:
                inv = self.store.load(row.id)
                if inv:
                    results.append(inv)
            return results
        finally:
            session.close()
