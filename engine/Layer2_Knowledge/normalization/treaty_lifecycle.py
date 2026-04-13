"""
Treaty Lifecycle Manager — Temporal Document Status Tracking
============================================================
Layer 2 Rule: Store the facts about document status.
              Don't interpret what they mean (that's Layer 3).

This module tracks the lifecycle of legal/political documents:
    signed → ratified → effective → amended → suspended → terminated

Layer 3's temporal_reasoner uses this metadata to decide:
    "Was this treaty active when the event happened?"

This single module prevents the catastrophic error of reasoning
about a terminated treaty as if it's still in force.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import json
import os


class TreatyStatus(Enum):
    """Lifecycle status of a legal document."""
    DRAFT = "draft"                  # Not yet signed
    SIGNED = "signed"                # Signed, awaiting ratification
    RATIFIED = "ratified"            # Ratified by required parties
    EFFECTIVE = "effective"          # Currently in force
    AMENDED = "amended"              # Modified (new version active)
    SUSPENDED = "suspended"          # Temporarily not in force
    TERMINATED = "terminated"        # Permanently ended
    REPLACED = "replaced"            # Superseded by new agreement
    WITHDRAWN = "withdrawn"          # Party withdrew


@dataclass
class TreatyRecord:
    """
    Lifecycle record for a treaty or international agreement.

    Example:
        TreatyRecord(
            treaty_id="indus_waters_1960",
            title="Indus Waters Treaty",
            parties=["IND", "PAK"],
            signed_date="1960-09-19",
            effective_date="1960-09-19",
            status=TreatyStatus.EFFECTIVE,
        )
    """
    treaty_id: str
    title: str
    parties: List[str]
    document_type: str = "treaty"               # treaty, agreement, MoU, protocol

    # Lifecycle dates
    signed_date: Optional[str] = None           # YYYY-MM-DD
    ratified_date: Optional[str] = None
    effective_date: Optional[str] = None
    amended_date: Optional[str] = None
    amendment_details: Optional[str] = None
    suspended_date: Optional[str] = None
    suspension_reason: Optional[str] = None
    terminated_date: Optional[str] = None
    termination_reason: Optional[str] = None

    # Replacement chain
    replaced_by: Optional[str] = None           # treaty_id of replacement
    replaces: Optional[str] = None              # treaty_id this replaces

    # Current status
    status: TreatyStatus = TreatyStatus.EFFECTIVE

    # Metadata
    source: str = "unknown"                     # Where we found this data
    topics: List[str] = field(default_factory=list)
    notes: Optional[str] = None

    def is_active_at(self, date: str) -> bool:
        """
        Check if treaty was active at a specific date.

        PURE DATA CHECK — no reasoning about implications.

        Args:
            date: ISO date string (YYYY-MM-DD)

        Returns:
            True if treaty was in force at that date.
        """
        # Must be effective to be active
        if self.status in (TreatyStatus.TERMINATED, TreatyStatus.REPLACED,
                           TreatyStatus.WITHDRAWN, TreatyStatus.DRAFT):
            # Even if date is before termination, check dates
            if self.terminated_date and date < self.terminated_date:
                if self.effective_date and date >= self.effective_date:
                    return True
            return False

        if self.status == TreatyStatus.SUSPENDED:
            # Suspended: was active before suspension
            if self.suspended_date and date < self.suspended_date:
                if self.effective_date and date >= self.effective_date:
                    return True
            return False

        # Active statuses: SIGNED, RATIFIED, EFFECTIVE, AMENDED
        if self.effective_date and date < self.effective_date:
            return False  # Not yet effective

        return True

    def to_dict(self) -> Dict:
        """Serialize for storage/API."""
        return {
            "treaty_id": self.treaty_id,
            "title": self.title,
            "parties": self.parties,
            "document_type": self.document_type,
            "status": self.status.value,
            "signed_date": self.signed_date,
            "effective_date": self.effective_date,
            "amended_date": self.amended_date,
            "suspended_date": self.suspended_date,
            "terminated_date": self.terminated_date,
            "replaced_by": self.replaced_by,
            "replaces": self.replaces,
            "topics": self.topics,
            "notes": self.notes,
        }


class TreatyLifecycleManager:
    """
    Storage and lookup for treaty lifecycle records.

    This is a Layer 2 component — it stores and retrieves facts.
    Layer 3 uses this to answer: "Was Treaty X active when Event Y happened?"
    """

    def __init__(self, storage_path: str = None):
        self._treaties: Dict[str, TreatyRecord] = {}
        self._storage_path = storage_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "treaty_registry.json"
        )
        self._load()

    def _load(self):
        """Load treaty records from disk."""
        if os.path.exists(self._storage_path):
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for rec in data:
                    rec["status"] = TreatyStatus(rec.get("status", "effective"))
                    self._treaties[rec["treaty_id"]] = TreatyRecord(**rec)
            except Exception:
                self._treaties = {}

    def _save(self):
        """Persist treaty records to disk."""
        os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
        records = [t.to_dict() for t in self._treaties.values()]
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

    def register(self, record: TreatyRecord):
        """Register or update a treaty record."""
        self._treaties[record.treaty_id] = record
        self._save()

    def get(self, treaty_id: str) -> Optional[TreatyRecord]:
        """Look up a treaty by ID."""
        return self._treaties.get(treaty_id)

    def find_by_parties(self, *parties: str) -> List[TreatyRecord]:
        """Find all treaties involving the given parties."""
        results = []
        party_set = set(p.upper() for p in parties)
        for t in self._treaties.values():
            treaty_parties = set(p.upper() for p in t.parties)
            if party_set.issubset(treaty_parties):
                results.append(t)
        return results

    def find_active_at(self, date: str, parties: List[str] = None) -> List[TreatyRecord]:
        """Find all treaties active at a given date, optionally filtered by parties."""
        results = []
        for t in self._treaties.values():
            if t.is_active_at(date):
                if parties:
                    party_set = set(p.upper() for p in parties)
                    treaty_parties = set(p.upper() for p in t.parties)
                    if not party_set.issubset(treaty_parties):
                        continue
                results.append(t)
        return results

    def update_status(self, treaty_id: str, new_status: TreatyStatus,
                      date: str = None, reason: str = None,
                      replaced_by: str = None):
        """
        Update treaty lifecycle status.

        This is how the system learns that a treaty was terminated,
        suspended, or replaced.
        """
        treaty = self._treaties.get(treaty_id)
        if treaty is None:
            raise ValueError(f"Treaty not found: {treaty_id}")

        treaty.status = new_status

        if new_status == TreatyStatus.SUSPENDED and date:
            treaty.suspended_date = date
            treaty.suspension_reason = reason
        elif new_status == TreatyStatus.TERMINATED and date:
            treaty.terminated_date = date
            treaty.termination_reason = reason
        elif new_status == TreatyStatus.REPLACED and replaced_by:
            treaty.replaced_by = replaced_by
        elif new_status == TreatyStatus.AMENDED and date:
            treaty.amended_date = date
            treaty.amendment_details = reason

        self._save()

    def count(self) -> int:
        """Total registered treaties."""
        return len(self._treaties)


# ═══════════════════════════════════════════════════════════════
# Module-level Singleton
# ═══════════════════════════════════════════════════════════════
treaty_manager = TreatyLifecycleManager()

__all__ = [
    "TreatyLifecycleManager", "treaty_manager",
    "TreatyRecord", "TreatyStatus",
]
