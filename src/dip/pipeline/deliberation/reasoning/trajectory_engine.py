"""
Phase 10: Trajectory / Early Warning Engine.

Produces forward-looking probabilistic forecasts:
  - 7-day trajectory
  - 14-day trajectory
  - 30-day trajectory

For each horizon, produces a distribution across conflict states:
  PEACE, CRISIS, LIMITED_CONFLICT, ACTIVE_CONFLICT, FULL_WAR

Also computes:
  - Black-swan risk (low-probability, high-impact events)
  - Early warning triggers (threshold crossings)
"""

import logging
import math
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from dip.pipeline.deliberation.reasoning.belief_revision import BeliefTrajectory
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus

logger = logging.getLogger("Layer5.TrajectoryEngine")


CONFLICT_STATES = ["PEACE", "CRISIS", "LIMITED_CONFLICT", "ACTIVE_CONFLICT", "FULL_WAR"]


class StateDistribution(BaseModel):
    """Probability distribution across conflict states at a given horizon."""
    horizon_days: int
    probabilities: Dict[str, float]  # state -> probability
    dominant_state: str
    confidence: float
    black_swan_risk: float = 0.0


class EarlyWarning(BaseModel):
    """An early warning trigger."""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    trigger_type: str  # THRESHOLD_CROSSING, MOMENTUM_SPIKE, PERSISTENCE_ALERT
    agent: str
    state: str
    current_probability: float
    threshold: float
    message: str


class TrajectoryEngine:
    """
    Uses the Belief Trajectory data from Phase 9 to project
    forward-looking conflict state distributions.
    """

    def __init__(self, belief_trajectory: BeliefTrajectory, message_bus: MessageBus):
        self.bt = belief_trajectory
        self.bus = message_bus
        self.early_warnings: List[EarlyWarning] = []

    def project_state_distribution(self, horizon_days: int) -> StateDistribution:
        """
        Project a probability distribution across conflict states
        at the given horizon, using agent belief trajectories and momentum.
        """
        # Gather current agent beliefs and momentum
        agent_probs: Dict[str, float] = {}
        agent_momentum: Dict[str, float] = {}

        for agent in self.bt.trajectories:
            latest = self.bt.get_latest(agent)
            if latest:
                agent_probs[agent] = latest.probability
                agent_momentum[agent] = self.bt.compute_momentum(agent)

        if not agent_probs:
            # No data — return uniform distribution
            uniform = {s: 1.0 / len(CONFLICT_STATES) for s in CONFLICT_STATES}
            return StateDistribution(
                horizon_days=horizon_days,
                probabilities=uniform,
                dominant_state="CRISIS",
                confidence=0.1,
                black_swan_risk=0.05,
            )

        # Compute weighted average probability across agents
        avg_prob = sum(agent_probs.values()) / len(agent_probs)
        avg_momentum = sum(agent_momentum.values()) / len(agent_momentum) if agent_momentum else 0.0

        # Project forward using momentum * horizon scaling
        # Longer horizons amplify uncertainty
        decay = 1.0 / (1.0 + 0.02 * horizon_days)  # confidence decay
        projected = avg_prob + avg_momentum * (horizon_days / 7.0) * decay
        projected = max(0.0, min(1.0, projected))

        # Map projected probability to a state distribution
        dist = self._probability_to_distribution(projected)

        # Black-swan risk: probability of tail events
        black_swan = dist.get("FULL_WAR", 0.0) + 0.01 * horizon_days
        black_swan = min(black_swan, 0.30)

        # Find dominant state
        dominant = max(dist, key=dist.get)

        return StateDistribution(
            horizon_days=horizon_days,
            probabilities={k: round(v, 4) for k, v in dist.items()},
            dominant_state=dominant,
            confidence=round(decay, 3),
            black_swan_risk=round(black_swan, 4),
        )

    def _probability_to_distribution(self, p: float) -> Dict[str, float]:
        """
        Map a single projected conflict probability (0-1) to a distribution
        across the 5 conflict states using a simple triangular kernel.
        """
        # Centers for each state on the 0-1 scale
        centers = {
            "PEACE": 0.1,
            "CRISIS": 0.3,
            "LIMITED_CONFLICT": 0.5,
            "ACTIVE_CONFLICT": 0.7,
            "FULL_WAR": 0.9,
        }

        raw = {}
        for state, center in centers.items():
            distance = abs(p - center)
            # Gaussian-like kernel
            raw[state] = math.exp(-0.5 * (distance / 0.15) ** 2)

        # Normalize
        total = sum(raw.values())
        return {s: v / total for s, v in raw.items()}

    def generate_forecast(self) -> Dict:
        """
        Generate the full forecast output:
          - 7-day, 14-day, 30-day trajectories
          - Early warnings
        """
        horizons = [7, 14, 30]
        forecasts = {}

        for h in horizons:
            dist = self.project_state_distribution(h)
            forecasts[f"{h}_day"] = dist.model_dump()

        # Check for early warning triggers
        self._check_early_warnings()

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "trajectories": forecasts,
            "early_warnings": [w.model_dump() for w in self.early_warnings],
            "agent_summary": self.bt.summary(),
        }

    def _check_early_warnings(self):
        """Check all agents for threshold crossings and momentum spikes."""
        ESCALATION_THRESHOLD = 0.65
        MOMENTUM_SPIKE_THRESHOLD = 0.10

        for agent in self.bt.trajectories:
            latest = self.bt.get_latest(agent)
            if not latest:
                continue

            # Threshold crossing
            if latest.probability >= ESCALATION_THRESHOLD:
                self.early_warnings.append(
                    EarlyWarning(
                        trigger_type="THRESHOLD_CROSSING",
                        agent=agent,
                        state=latest.state,
                        current_probability=latest.probability,
                        threshold=ESCALATION_THRESHOLD,
                        message=f"{agent} probability {latest.probability:.2f} exceeds "
                        f"escalation threshold {ESCALATION_THRESHOLD}",
                    )
                )

            # Momentum spike
            momentum = self.bt.compute_momentum(agent)
            if abs(momentum) >= MOMENTUM_SPIKE_THRESHOLD:
                direction = "escalating" if momentum > 0 else "de-escalating"
                self.early_warnings.append(
                    EarlyWarning(
                        trigger_type="MOMENTUM_SPIKE",
                        agent=agent,
                        state=latest.state,
                        current_probability=latest.probability,
                        threshold=MOMENTUM_SPIKE_THRESHOLD,
                        message=f"{agent} momentum {momentum:+.3f} is rapidly {direction}",
                    )
                )

            # Persistence alert
            persistence = self.bt.compute_persistence(agent)
            if persistence >= 3:
                self.early_warnings.append(
                    EarlyWarning(
                        trigger_type="PERSISTENCE_ALERT",
                        agent=agent,
                        state=latest.state,
                        current_probability=latest.probability,
                        threshold=3.0,
                        message=f"{agent} has sustained directional trend for {persistence} revisions",
                    )
                )
