"""
Phase 9: Belief Revision & Temporal Memory.

Tracks how agent beliefs evolve over time and stores the *reason*
for each probability change, producing a belief trajectory rather
than a collection of isolated predictions.

Stores:
  T1: Security = 0.72 (reason: troop movement detected)
  T2: Security = 0.61 (reason: satellite imagery shows withdrawal)
  T3: Security = 0.77 (reason: new SIGINT intercept contradicts withdrawal)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from dip.pipeline.deliberation.reasoning.message_bus import MessageBus

logger = logging.getLogger("Layer4.BeliefRevision")


class BeliefSnapshot(BaseModel):
    """A single point on the belief trajectory."""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agent: str
    state: str
    probability: float
    previous_probability: Optional[float] = None
    delta: float = 0.0
    reason: str = ""
    evidence_ids: List[str] = Field(default_factory=list)
    round_num: int = 0


class BeliefTrajectory:
    """
    Maintains a time-ordered list of BeliefSnapshots per agent,
    enabling temporal analysis like momentum, persistence, and spikes.
    """

    def __init__(self):
        # agent_name -> list of snapshots, ordered chronologically
        self.trajectories: Dict[str, List[BeliefSnapshot]] = {}

    def record(
        self,
        agent: str,
        state: str,
        probability: float,
        reason: str = "",
        evidence_ids: Optional[List[str]] = None,
        round_num: int = 0,
    ):
        if agent not in self.trajectories:
            self.trajectories[agent] = []

        prev = self.trajectories[agent][-1].probability if self.trajectories[agent] else None
        delta = (probability - prev) if prev is not None else 0.0

        snap = BeliefSnapshot(
            agent=agent,
            state=state,
            probability=probability,
            previous_probability=prev,
            delta=delta,
            reason=reason,
            evidence_ids=evidence_ids or [],
            round_num=round_num,
        )
        self.trajectories[agent].append(snap)

        direction = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        logger.info(
            f"[BeliefRevision] {agent}: {state} {prev or '?'} {direction} {probability} "
            f"(Δ={delta:+.3f}) reason='{reason}'"
        )

    def get_trajectory(self, agent: str) -> List[BeliefSnapshot]:
        return self.trajectories.get(agent, [])

    def get_latest(self, agent: str) -> Optional[BeliefSnapshot]:
        traj = self.trajectories.get(agent, [])
        return traj[-1] if traj else None

    def compute_momentum(self, agent: str, window: int = 3) -> float:
        """
        Average delta over the last `window` snapshots.
        Positive = escalating trend, Negative = de-escalating trend.
        """
        traj = self.trajectories.get(agent, [])
        if len(traj) < 2:
            return 0.0
        recent = traj[-window:]
        deltas = [s.delta for s in recent]
        return sum(deltas) / len(deltas)

    def detect_spike(self, agent: str, threshold: float = 0.15) -> bool:
        """
        Returns True if the latest delta exceeds the threshold.
        A spike means a sudden, large shift in belief.
        """
        traj = self.trajectories.get(agent, [])
        if not traj:
            return False
        return abs(traj[-1].delta) >= threshold

    def compute_persistence(self, agent: str) -> int:
        """
        How many consecutive snapshots has the agent maintained
        the same directional trend (all positive deltas or all negative)?
        """
        traj = self.trajectories.get(agent, [])
        if len(traj) < 2:
            return 0

        count = 1
        last_direction = traj[-1].delta >= 0
        for snap in reversed(traj[:-1]):
            if (snap.delta >= 0) == last_direction:
                count += 1
            else:
                break
        return count

    def summary(self) -> Dict:
        """Return a full summary of all agents' belief trajectories."""
        result = {}
        for agent in self.trajectories:
            latest = self.get_latest(agent)
            result[agent] = {
                "current_probability": latest.probability if latest else None,
                "current_state": latest.state if latest else None,
                "total_revisions": len(self.trajectories[agent]),
                "momentum": round(self.compute_momentum(agent), 4),
                "spike_detected": self.detect_spike(agent),
                "persistence": self.compute_persistence(agent),
            }
        return result
