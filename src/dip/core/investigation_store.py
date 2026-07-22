"""
Investigation Store — File-System Persistence for DIP 3.0
==========================================================

Every investigation gets a real folder tree on disk:

    investigations/
        INV-2026-00152/
            metadata.json       # Full Investigation object
            evidence/           # Raw observations, signals
            reports/            # Generated dossiers
            hypotheses/         # Expert reasoning snapshots
            timeline/           # Append-only event log (JSONL)
            world_model/        # StateContext snapshots per version
            feedback/           # HITL corrections
            versions/           # Versioned snapshots of the full investigation
            datasets/           # SFT/DPO training exports

The folder is the source of truth.
The SQLite DB in investigation_memory.py is just an index for fast queries.
"""

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from dip.core.schema import (
    Investigation,
    TimelineEvent,
    VALID_TRANSITIONS,
)

logger = logging.getLogger("Core.InvestigationStore")

# Subdirectories created for every investigation
_SUBDIRS = [
    "evidence",
    "reports",
    "hypotheses",
    "timeline",
    "world_model",
    "feedback",
    "versions",
    "datasets",
]


class InvalidTransitionError(Exception):
    """Raised when an invalid state machine transition is attempted."""
    pass


class InvestigationStore:
    """
    File-system persistence for Investigations.

    Each investigation is a directory containing metadata.json and
    subdirectories for evidence, reports, timeline, etc.
    """

    def __init__(self, root_dir: str = "investigations"):
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Folder Management
    # ------------------------------------------------------------------

    def _inv_dir(self, investigation_id: str) -> Path:
        return self.root / investigation_id

    def _ensure_dirs(self, investigation_id: str) -> Path:
        """Create the full folder tree for an investigation."""
        inv_dir = self._inv_dir(investigation_id)
        inv_dir.mkdir(parents=True, exist_ok=True)
        for sub in _SUBDIRS:
            (inv_dir / sub).mkdir(exist_ok=True)
        return inv_dir

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, investigation: Investigation) -> Path:
        """Create a new investigation folder and persist metadata."""
        inv_dir = self._ensure_dirs(investigation.investigation_id)
        self._write_metadata(investigation)
        self.append_timeline(
            investigation.investigation_id,
            TimelineEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type="CREATED",
                description=f"Investigation created: {investigation.title}",
                layer="Layer0",
            ),
        )
        logger.info(f"Created investigation folder: {inv_dir}")
        return inv_dir

    def save(self, investigation: Investigation) -> None:
        """Save the current state of an investigation to disk."""
        investigation.updated_at = datetime.now(timezone.utc).isoformat()
        self._ensure_dirs(investigation.investigation_id)
        self._write_metadata(investigation)

    def load(self, investigation_id: str) -> Optional[Investigation]:
        """Load an investigation from its folder."""
        meta_path = self._inv_dir(investigation_id) / "metadata.json"
        if not meta_path.exists():
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Investigation(**data)
        except Exception as e:
            logger.error(f"Failed to load investigation {investigation_id}: {e}")
            return None

    def list_all(self) -> List[Investigation]:
        """List all investigations by scanning the root directory."""
        results = []
        if not self.root.exists():
            return results
        for entry in sorted(self.root.iterdir()):
            if entry.is_dir() and (entry / "metadata.json").exists():
                inv = self.load(entry.name)
                if inv:
                    results.append(inv)
        return results

    def list_by_status(self, status: str) -> List[Investigation]:
        """List investigations filtered by status."""
        return [inv for inv in self.list_all() if inv.status == status]

    # ------------------------------------------------------------------
    # State Machine
    # ------------------------------------------------------------------

    def transition(self, investigation: Investigation, new_status: str) -> None:
        """
        Transition the investigation to a new state.
        Raises InvalidTransitionError if the transition is not allowed.
        """
        current = investigation.status
        allowed = VALID_TRANSITIONS.get(current, [])
        if new_status not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from {current} to {new_status}. "
                f"Allowed: {allowed}"
            )
        old_status = investigation.status
        investigation.status = new_status
        investigation.updated_at = datetime.now(timezone.utc).isoformat()
        self.save(investigation)
        self.append_timeline(
            investigation.investigation_id,
            TimelineEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type="STATE_CHANGE",
                description=f"State: {old_status} → {new_status}",
                layer="Layer0",
                metadata={"from": old_status, "to": new_status},
            ),
        )
        logger.info(f"[{investigation.investigation_id}] {old_status} → {new_status}")

    # ------------------------------------------------------------------
    # Timeline (append-only JSONL)
    # ------------------------------------------------------------------

    def append_timeline(self, investigation_id: str, event: TimelineEvent) -> None:
        """Append an event to the investigation timeline (JSONL)."""
        timeline_path = self._inv_dir(investigation_id) / "timeline" / "events.jsonl"
        timeline_path.parent.mkdir(parents=True, exist_ok=True)
        with open(timeline_path, "a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")

    def read_timeline(self, investigation_id: str) -> List[TimelineEvent]:
        """Read the full timeline for an investigation."""
        timeline_path = self._inv_dir(investigation_id) / "timeline" / "events.jsonl"
        if not timeline_path.exists():
            return []
        events = []
        with open(timeline_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(TimelineEvent(**json.loads(line)))
        return events

    # ------------------------------------------------------------------
    # Evidence Persistence
    # ------------------------------------------------------------------

    def save_evidence(
        self,
        investigation_id: str,
        observations: list = None,
        signals: list = None,
        entities: list = None,
        claims: list = None,
    ) -> None:
        """Save extracted evidence to the investigation's evidence folder."""
        evidence_dir = self._inv_dir(investigation_id) / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)

        if observations:
            self._write_json(
                evidence_dir / "observations.json",
                [o.model_dump() if hasattr(o, "model_dump") else o for o in observations],
            )
        if signals:
            self._write_json(
                evidence_dir / "signals.json",
                [s.model_dump() if hasattr(s, "model_dump") else s for s in signals],
            )
        if entities:
            self._write_json(
                evidence_dir / "entities.json",
                [e.model_dump() if hasattr(e, "model_dump") else e for e in entities],
            )
        if claims:
            self._write_json(
                evidence_dir / "claims.json",
                [c.model_dump() if hasattr(c, "model_dump") else c for c in claims],
            )

        self.append_timeline(
            investigation_id,
            TimelineEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type="EVIDENCE_SAVED",
                description=f"Saved evidence: {len(observations or [])} obs, {len(signals or [])} signals",
                layer="Layer2",
            ),
        )

    # ------------------------------------------------------------------
    # World Model Snapshots
    # ------------------------------------------------------------------

    def save_world_model(self, investigation_id: str, state_context, version: int = 1) -> None:
        """Save a versioned snapshot of the world model (StateContext)."""
        wm_dir = self._inv_dir(investigation_id) / "world_model"
        wm_dir.mkdir(parents=True, exist_ok=True)
        filename = f"state_v{version}.json"
        data = state_context.model_dump() if hasattr(state_context, "model_dump") else state_context
        self._write_json(wm_dir / filename, data)
        self.append_timeline(
            investigation_id,
            TimelineEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type="WORLD_MODEL_SAVED",
                description=f"World model snapshot v{version} saved",
                layer="Layer3",
            ),
        )

    # ------------------------------------------------------------------
    # Hypotheses
    # ------------------------------------------------------------------

    def save_hypotheses(self, investigation_id: str, hypotheses: list) -> None:
        """Save expert hypotheses."""
        hyp_dir = self._inv_dir(investigation_id) / "hypotheses"
        hyp_dir.mkdir(parents=True, exist_ok=True)
        data = [h.model_dump() if hasattr(h, "model_dump") else h for h in hypotheses]
        self._write_json(hyp_dir / "hypotheses.json", data)

    # ------------------------------------------------------------------
    # Version Snapshots
    # ------------------------------------------------------------------

    def snapshot_version(self, investigation: Investigation) -> None:
        """Save a full versioned snapshot of the investigation."""
        ver_dir = self._inv_dir(investigation.investigation_id) / "versions"
        ver_dir.mkdir(parents=True, exist_ok=True)
        filename = f"v{investigation.version}.json"
        self._write_json(ver_dir / filename, investigation.model_dump())
        logger.info(f"[{investigation.investigation_id}] Snapshot v{investigation.version} saved")

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _write_metadata(self, investigation: Investigation) -> None:
        meta_path = self._inv_dir(investigation.investigation_id) / "metadata.json"
        self._write_json(meta_path, investigation.model_dump())

    def _write_json(self, path: Path, data) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
