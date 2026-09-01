"""
Stopping Criteria — When to Stop Collecting
=============================================

Instead of fixed collection, the planner decides when enough evidence exists.

Criteria:
    - Minimum observations reached
    - Maximum rounds exhausted
    - Budget exhausted
"""

import logging

from dip.pipeline.collection.budget_manager import BudgetManager

logger = logging.getLogger("Layer1.StoppingCriteria")


class StoppingCriteria:
    """
    Determines when collection should stop.

    Mirrors how human analysts decide: "Do I have enough evidence?"
    """

    def __init__(
        self,
        min_observations: int = 20,
        max_rounds: int = 3,
    ):
        self.min_observations = min_observations
        self.max_rounds = max_rounds
        self._reason = ""

    @property
    def reason(self) -> str:
        return self._reason

    def should_stop(
        self,
        observations_count: int,
        round_num: int,
        budget_exhausted: bool,
    ) -> bool:
        """
        Returns True if collection should stop.

        Stop if:
            1. We have enough observations AND completed at least 1 round
            2. We've hit max rounds
            3. Budget is exhausted
        """
        if budget_exhausted:
            self._reason = "Budget exhausted"
            logger.info(f"Stopping: {self._reason}")
            return True

        if round_num >= self.max_rounds:
            self._reason = f"Max rounds reached ({self.max_rounds})"
            logger.info(f"Stopping: {self._reason}")
            return True

        if observations_count >= self.min_observations and round_num >= 1:
            self._reason = f"Sufficient evidence ({observations_count} >= {self.min_observations})"
            logger.info(f"Stopping: {self._reason}")
            return True

        self._reason = ""
        return False
