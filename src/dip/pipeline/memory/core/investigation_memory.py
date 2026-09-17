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
from pathlib import Path
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

    Relative paths resolve under the central DATA_DIR (never the process
    working directory). Legacy working-directory files (``investigations.db``
    / ``investigations/``) are copied forward once — never moved or deleted.
    """

    def __init__(self, db_path: str | None = None, store_root: str | None = None):
        from dip.core.Config.config import resolve_data_path

        db_path = resolve_data_path(db_path or "", "investigations.db")
        store_root = resolve_data_path(store_root or "", "investigations")
        self._migrate_legacy_files(db_path, store_root)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.store = InvestigationStore(root_dir=store_root)

    @staticmethod
    def _migrate_legacy_files(db_path: str, store_root: str) -> None:
        """One-time copy of working-directory data into DATA_DIR.

        Copies only when the destination is missing, so user data is never
        destroyed or overwritten. Runs at construction, not at import.
        """
        import logging
        import shutil

        logger = logging.getLogger("Memory.InvestigationMemory")
        try:
            legacy_db = Path.cwd() / "investigations.db"
            if (
                legacy_db.is_file()
                and not Path(db_path).exists()
                and Path(db_path).resolve() != legacy_db.resolve()
                and legacy_db.read_bytes()[:16] == b"SQLite format 3\x00"
            ):
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy_db, db_path)
                logger.info("Migrated legacy investigations.db from working directory (copy; original kept).")
            legacy_store = Path.cwd() / "investigations"
            if legacy_store.is_dir() and not Path(store_root).exists() and Path(store_root).resolve() != legacy_store.resolve():
                shutil.copytree(legacy_store, store_root)
                logger.info("Migrated legacy investigations/ from working directory (copy; original kept).")
        except Exception as exc:  # migration must never break startup
            logger.debug("Legacy data migration skipped: %s", exc)

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
