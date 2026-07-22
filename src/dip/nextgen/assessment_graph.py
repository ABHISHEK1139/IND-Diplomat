from __future__ import annotations

"""Durable assessment blackboard and lightweight graph facade.

Provides an append-only `AssessmentBlackboard` used throughout the pipeline
to record phase events, which can be backed by LangGraph when installed.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from .contracts import AssessmentGoal, BlackboardEvent, create_assessment_goal
from .oss_adapters import OSSAdapterRegistry


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PipelinePhase(str):
    GOAL_INTAKE = "goal_intake"
    COLLECTION = "collection"
    FUZZY_PROJECTION = "fuzzy_projection"
    SRE = "sre"
    COUNCIL = "council"
    INVESTIGATION = "investigation"
    GATE = "gate"
    REPORT = "report"
    LEARNING = "learning"


DEFAULT_PHASES: List[str] = [
    PipelinePhase.GOAL_INTAKE,
    PipelinePhase.COLLECTION,
    PipelinePhase.FUZZY_PROJECTION,
    PipelinePhase.SRE,
    PipelinePhase.COUNCIL,
    PipelinePhase.INVESTIGATION,
    PipelinePhase.GATE,
    PipelinePhase.REPORT,
    PipelinePhase.LEARNING,
]


class AssessmentBlackboard:
    """Append-only blackboard storing `BlackboardEvent` entries.

    By default this writes to `checkpoint_dir/<trace_id>.jsonl`. If LangGraph
    is installed, the registry can be extended to use LangGraph for durable
    checkpoints and streaming reads.
    """

    def __init__(self, trace_id: str, checkpoint_dir: Optional[Path] = None):
        self.trace_id = trace_id
        self.checkpoint_dir = Path(checkpoint_dir or Path(__file__).resolve().parent / ".." / "data" / "blackboards")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.checkpoint_dir / f"{self.trace_id}.jsonl"
        self.events: List[BlackboardEvent] = []
        self.state: Dict[str, Any] = {}
        self.registry = OSSAdapterRegistry()

    def post(self, phase: str, event_type: str, payload: Optional[Dict[str, Any]] = None, *, source: str = "dip2.nextgen") -> BlackboardEvent:
        event = BlackboardEvent(trace_id=self.trace_id, phase=phase, event_type=event_type, payload=payload or {}, source=source)
        self.events.append(event)
        # append to disk
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        except Exception:
            pass
        return event

    def history(self, phase: Optional[str] = None) -> List[BlackboardEvent]:
        if phase is None:
            return list(self.events)
        return [e for e in self.events if e.phase == phase]

    def load(self) -> None:
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    ev = BlackboardEvent.model_validate_json(line)
                    self.events.append(ev)
                except Exception:
                    continue


class HeadOfStatePipelineGraph:
    """Facade that creates an `AssessmentGoal` and `AssessmentBlackboard`.

    If LangGraph is available, this can be extended to use it for a durable
    execution graph. For now this provides a stable API and checkpoint
    directory management.
    """

    def __init__(self, checkpoint_dir: Path | str):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def start(self, objective: str, country: str = "UNKNOWN") -> tuple[AssessmentGoal, AssessmentBlackboard]:
        goal = create_assessment_goal(objective, country=country)
        bb = AssessmentBlackboard(trace_id=goal.trace_id, checkpoint_dir=self.checkpoint_dir)
        bb.post(PipelinePhase.GOAL_INTAKE, "goal.created", {"objective": objective, "country": country})
        # Persist initial phase
        try:
            self.save_phase(goal, PipelinePhase.GOAL_INTAKE, bb)
        except Exception:
            pass
        return goal, bb

    def save_phase(self, goal: AssessmentGoal, phase: str, blackboard: AssessmentBlackboard) -> None:
        out = {
            "trace_id": goal.trace_id,
            "phase": phase,
            "timestamp": _now(),
            "events": [e.model_dump(mode="json") for e in blackboard.history()],
            "state": blackboard.state,
        }
        path = Path(self.checkpoint_dir) / f"{goal.trace_id}-{phase}.json"
        try:
            # Try to use a checkpoint manager if available
            from engine.Core.checkpoint_manager import CheckpointManager  # type: ignore
            mgr = CheckpointManager(goal.trace_id, checkpoint_dir=self.checkpoint_dir)
            mgr.save_checkpoint(phase, out, fmt="json")
        except Exception:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(out, f, indent=2)
            except Exception:
                pass
        # Also write a simple per-trace phase file under <checkpoint_dir>/<trace_id>/<phase>.json
        try:
            trace_dir = Path(self.checkpoint_dir) / goal.trace_id
            trace_dir.mkdir(parents=True, exist_ok=True)
            per_phase = trace_dir / f"{phase}.json"
            with open(per_phase, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
        except Exception:
            pass
