"""
Phase 13: Calibration / Learning Loop.

Closes the loop:
  Forecast -> Outcome -> Error -> Calibration -> Update parameters -> Better future forecast

Implements:
  - Forecast archiving (store every prediction with its context)
  - Outcome recording (when ground truth becomes available)
  - Calibration curve computation
  - Auto-adjustment of agent weights based on historical accuracy
"""

import logging
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone

logger = logging.getLogger("Layer8.Calibration")


class ArchivedForecast(BaseModel):
    """A stored forecast awaiting outcome comparison."""
    forecast_id: str
    query: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    predicted_state: str
    predicted_probability: float
    agent_beliefs: Dict[str, float] = Field(default_factory=dict)
    actual_outcome: Optional[str] = None
    actual_probability: Optional[float] = None
    error: Optional[float] = None
    resolved: bool = False


class AgentCalibration(BaseModel):
    """Calibration data for a single agent."""
    agent: str
    total_forecasts: int = 0
    total_error: float = 0.0
    mean_absolute_error: float = 0.0
    brier_contribution: float = 0.0
    weight: float = 1.0  # Agent's current weight in the ensemble


class CalibrationLoop:
    """
    Maintains a forecast archive and computes per-agent calibration
    to adjust ensemble weights over time.
    """

    def __init__(self):
        self.archive: List[ArchivedForecast] = []
        self.agent_calibrations: Dict[str, AgentCalibration] = {}

    def archive_forecast(
        self,
        forecast_id: str,
        query: str,
        predicted_state: str,
        predicted_probability: float,
        agent_beliefs: Dict[str, float],
    ):
        """Store a new forecast for future calibration."""
        entry = ArchivedForecast(
            forecast_id=forecast_id,
            query=query,
            predicted_state=predicted_state,
            predicted_probability=predicted_probability,
            agent_beliefs=agent_beliefs,
        )
        self.archive.append(entry)
        logger.info(f"[Calibration] Archived forecast {forecast_id}: {predicted_state} @ {predicted_probability}")

    def record_outcome(
        self,
        forecast_id: str,
        actual_outcome: str,
        actual_probability: float,
    ):
        """Record the ground truth outcome for a previously archived forecast."""
        for entry in self.archive:
            if entry.forecast_id == forecast_id and not entry.resolved:
                entry.actual_outcome = actual_outcome
                entry.actual_probability = actual_probability
                entry.error = abs(entry.predicted_probability - actual_probability)
                entry.resolved = True

                # Update per-agent calibration
                for agent, belief in entry.agent_beliefs.items():
                    self._update_agent_calibration(agent, belief, actual_probability)

                logger.info(
                    f"[Calibration] Resolved {forecast_id}: "
                    f"predicted={entry.predicted_probability:.3f} actual={actual_probability:.3f} "
                    f"error={entry.error:.3f}"
                )
                return

        logger.warning(f"[Calibration] Forecast {forecast_id} not found or already resolved.")

    def _update_agent_calibration(self, agent: str, predicted: float, actual: float):
        """Update calibration stats for a single agent."""
        if agent not in self.agent_calibrations:
            self.agent_calibrations[agent] = AgentCalibration(agent=agent)

        cal = self.agent_calibrations[agent]
        error = abs(predicted - actual)
        brier = (predicted - actual) ** 2

        cal.total_forecasts += 1
        cal.total_error += error
        cal.brier_contribution += brier
        cal.mean_absolute_error = cal.total_error / cal.total_forecasts

        # Adjust weight: better-calibrated agents get higher weight
        # Weight = 1 / (1 + MAE), so perfect agents get weight 1.0
        cal.weight = 1.0 / (1.0 + cal.mean_absolute_error)

        logger.debug(
            f"[Calibration] {agent}: MAE={cal.mean_absolute_error:.4f} "
            f"weight={cal.weight:.4f}"
        )

    def get_agent_weights(self) -> Dict[str, float]:
        """Get current calibrated weights for all agents."""
        return {
            agent: cal.weight
            for agent, cal in self.agent_calibrations.items()
        }

    def compute_calibration_curve(self, bins: int = 5) -> List[Dict]:
        """
        Compute a calibration curve: for each bin of predicted probability,
        what was the actual frequency?
        """
        resolved = [f for f in self.archive if f.resolved]
        if not resolved:
            return []

        bin_width = 1.0 / bins
        curve = []

        for i in range(bins):
            lower = i * bin_width
            upper = (i + 1) * bin_width
            in_bin = [
                f
                for f in resolved
                if lower <= f.predicted_probability < upper
            ]

            if in_bin:
                mean_predicted = sum(f.predicted_probability for f in in_bin) / len(in_bin)
                mean_actual = sum(f.actual_probability for f in in_bin) / len(in_bin)
                curve.append(
                    {
                        "bin_lower": round(lower, 2),
                        "bin_upper": round(upper, 2),
                        "count": len(in_bin),
                        "mean_predicted": round(mean_predicted, 4),
                        "mean_actual": round(mean_actual, 4),
                        "gap": round(abs(mean_predicted - mean_actual), 4),
                    }
                )

        return curve

    def summary(self) -> Dict:
        """Full calibration summary."""
        resolved = [f for f in self.archive if f.resolved]
        unresolved = [f for f in self.archive if not f.resolved]

        return {
            "total_archived": len(self.archive),
            "resolved": len(resolved),
            "unresolved": len(unresolved),
            "agent_calibrations": {
                agent: {
                    "mae": round(cal.mean_absolute_error, 4),
                    "weight": round(cal.weight, 4),
                    "total_forecasts": cal.total_forecasts,
                }
                for agent, cal in self.agent_calibrations.items()
            },
            "calibration_curve": self.compute_calibration_curve(),
        }
